import json
import logging
import subprocess
import time
import asyncio
from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from ib_insync import IB

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_config() -> dict:
    """Load configuration from config.json."""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, "r") as f:
        return json.load(f)


def send_telegram_message(token: str, chat_id: str, message: str) -> None:
    """Send message via Telegram bot."""
    try:
        response = requests.get(
            f'https://api.telegram.org/bot{token}/sendMessage',
            params={'chat_id': chat_id, 'text': message},
            timeout=10
        )
        if response.status_code != 200:
            logging.error(f"Failed to send Telegram message: HTTP {response.status_code}")
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")


def is_weekend(timezone_str: str) -> bool:
    """Check if current time is weekend in the specified timezone."""
    tz = ZoneInfo(timezone_str)
    now = datetime.now(tz)
    # Saturday = 5, Sunday = 6
    return now.weekday() >= 5


def is_in_maintenance_window(timezone_str: str, start_time: str, end_time: str) -> bool:
    """Check if current time is within the daily maintenance window."""
    tz = ZoneInfo(timezone_str)
    now = datetime.now(tz)

    start_hour, start_minute = map(int, start_time.split(":"))
    end_hour, end_minute = map(int, end_time.split(":"))

    start = dt_time(start_hour, start_minute)
    end = dt_time(end_hour, end_minute)
    current = now.time()

    return start <= current <= end


def is_paused(config: dict) -> tuple[bool, str]:
    """Check if monitoring should be paused based on pause windows."""
    pause_windows = config.get("pause_windows", {})

    # Check weekends
    weekend_config = pause_windows.get("weekends", {})
    if weekend_config:
        tz = weekend_config.get("timezone", "America/New_York")
        if is_weekend(tz):
            return True, f"Weekend in {tz}"

    # Check daily maintenance window
    maintenance_config = pause_windows.get("daily_maintenance", {})
    if maintenance_config:
        tz = maintenance_config.get("timezone", "America/Los_Angeles")
        start = maintenance_config.get("start_time", "23:45")
        end = maintenance_config.get("end_time", "23:55")
        if is_in_maintenance_window(tz, start, end):
            return True, f"Daily maintenance window ({start}-{end} {tz})"

    return False, ""


async def check_tws_api_health(host: str, port: int, client_id: int, timeout: int = 5) -> tuple[bool, str]:
    """Check the health of the TWS API using ib_insync."""
    logging.info(f"Attempting to connect to TWS API at {host}:{port}...")
    ib = IB()
    try:
        await asyncio.wait_for(ib.connectAsync(host, port, clientId=client_id), timeout=timeout)
        if not ib.isConnected():
            return False, "Failed to establish connection within timeout period."
        try:
            await asyncio.wait_for(ib.reqCurrentTimeAsync(), timeout=timeout)
        except Exception as e:
            return False, f"Failed to receive server time response: {e}"
        return True, "TWS API is healthy and responsive."
    except asyncio.TimeoutError:
        return False, "Connection or server time request timed out."
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"
    finally:
        if ib.isConnected():
            ib.disconnect()
            logging.info("Disconnected from TWS API.")


def stop_tws_process(port: int) -> bool:
    """Stop TWS process using PowerShell command."""
    cmd = f'powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort {port}).OwningProcess -Force"'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            logging.info(f"Successfully stopped TWS process on port {port}")
            return True
        else:
            logging.warning(f"Stop process command returned: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"Failed to stop TWS process: {e}")
        return False


def start_tws() -> bool:
    """Start TWS using IBC batch file."""
    cmd = r'C:\IBC_L\StartTWS.bat'
    cwd = r'C:\IBC_S'
    try:
        subprocess.Popen(cmd, shell=True, cwd=cwd)
        logging.info(f"Started TWS via StartTWS.bat (cwd={cwd})")
        return True
    except Exception as e:
        logging.error(f"Failed to start TWS: {e}")
        return False


async def restart_tws(config: dict) -> None:
    """Perform TWS restart sequence."""
    name = config["name"]
    port = config["port"]
    wait_after_stop = config.get("wait_after_stop", 30)

    # Send notification
    send_telegram_message(
        config["bot_token"],
        config["chat_id"],
        f"{name}: restarting TWS"
    )

    # Stop TWS process
    logging.info(f"Stopping TWS process on port {port}...")
    stop_tws_process(port)

    # Wait before restart
    logging.info(f"Waiting {wait_after_stop} seconds before starting TWS...")
    await asyncio.sleep(wait_after_stop)

    # Start TWS
    logging.info("Starting TWS...")
    start_tws()


async def main():
    config = load_config()

    name = config["name"]
    address = config["address"]
    port = config["port"]
    client_id = config.get("client_id", 1)
    check_interval = config.get("check_interval", 60)

    logging.info(f"Starting TWS monitoring service: {name}")
    send_telegram_message(
        config["bot_token"],
        config["chat_id"],
        f"{name}: TWS monitoring started"
    )

    while True:
        try:
            # Check if monitoring should be paused
            paused, reason = is_paused(config)
            if paused:
                logging.info(f"Monitoring paused: {reason}. Sleeping for {check_interval} seconds...")
                await asyncio.sleep(check_interval)
                continue

            # Check TWS health
            is_healthy, status_message = await check_tws_api_health(address, port, client_id)

            if is_healthy:
                logging.info(f"{status_message}. Sleeping for {check_interval} seconds...")
            else:
                logging.warning(f"TWS unhealthy: {status_message}")
                await restart_tws(config)

            await asyncio.sleep(check_interval)

        except KeyboardInterrupt:
            logging.info(f"Shutting down TWS monitoring service: {name}")
            send_telegram_message(
                config["bot_token"],
                config["chat_id"],
                f"{name}: TWS monitoring stopped"
            )
            break
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            await asyncio.sleep(check_interval)


if __name__ == '__main__':
    asyncio.run(main())
