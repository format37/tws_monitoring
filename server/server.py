import os
import logging
import requests
import time
import asyncio
from ib_insync import IB

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def check_tws_api_health(host="localhost", port=9999, timeout=5, client_id=10):
    """
    Check the health of the TWS API using ib_insync.
    Returns tuple of (is_healthy, status_message).
    """
    logging.info(f"Attempting to connect to TWS API at {host}:{port}...")
    ib = IB()
    try:
        await asyncio.wait_for(ib.connectAsync(host, port, clientId=client_id), timeout=timeout)
        if not ib.isConnected():
            return False, "Failed to establish connection within timeout period."
        # Request current server time to verify API responsiveness
        try:
            server_time = await asyncio.wait_for(ib.reqCurrentTimeAsync(), timeout=timeout)
        except Exception as e:
            return False, f"Failed to receive server time response: {e}"
        return True, f"TWS API is healthy and responsive. Server time: {server_time}"
    except asyncio.TimeoutError:
        return False, "Connection or server time request timed out."
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"
    finally:
        if ib.isConnected():
            ib.disconnect()
            logging.info("Disconnected from TWS API.")

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

async def main():
    # Load environment variables with defaults
    config = {
        'telegram_token': os.environ.get('BOT_TOKEN', ''),
        'chat_id': os.environ.get('CHAT_ID', ''),
        'normal_sleep': 60,  # Check every minute
        'fail_sleep': 60,    # Check every minute even if failed
        'hourly_reminder': int(os.environ.get('HOURLY_REMINDER', 3600)),  # 1 hour
        'host': os.environ.get('TWS_HOST', 'localhost'),
        'port': int(os.environ.get('TWS_PORT', 9999)),
        'client_id': int(os.environ.get('TWS_CLIENT_ID', 10))
    }

    # Validate required environment variables
    required_vars = {
        'BOT_TOKEN': 'telegram_token',
        'CHAT_ID': 'chat_id'
    }
    missing_vars = [env for env, key in required_vars.items() if not config[key]]
    if missing_vars:
        logging.error(
            f"Missing required environment variables: {', '.join(missing_vars)}. "
            "Required: BOT_TOKEN, CHAT_ID. Optional: TWS_HOST, TWS_PORT, NORMAL_SLEEP, FAIL_SLEEP, HOURLY_REMINDER."
        )
        return

    logging.info("Starting the TWS API monitoring service")
    send_telegram_message(
        config['telegram_token'],
        config['chat_id'],
        "TWS API monitoring started"
    )

    previous_is_healthy = None
    last_reminder_time = 0

    while True:
        try:
            current_time = time.time()
            is_healthy, status_message = await check_tws_api_health(
                host=config['host'],
                port=config['port'],
                client_id=config['client_id']
            )

            # Notify on health down (transition up->down or still down and hourly reminder)
            if previous_is_healthy is None or is_healthy != previous_is_healthy:
                # Status changed (either up->down or down->up)
                send_telegram_message(
                    config['telegram_token'],
                    config['chat_id'],
                    status_message
                )
                last_reminder_time = current_time
            elif not is_healthy and (current_time - last_reminder_time) >= config['hourly_reminder']:
                # Still down, send hourly reminder
                send_telegram_message(
                    config['telegram_token'],
                    config['chat_id'],
                    f"Reminder: {status_message}"
                )
                last_reminder_time = current_time

            previous_is_healthy = is_healthy

            sleep_time = config['normal_sleep'] if is_healthy else config['fail_sleep']
            logging.info(f"{status_message}. Sleeping for {sleep_time} seconds")
            await asyncio.sleep(sleep_time)

        except KeyboardInterrupt:
            logging.info("Shutting down TWS API monitoring service")
            send_telegram_message(
                config['telegram_token'],
                config['chat_id'],
                "TWS API monitoring stopped"
            )
            break
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            await asyncio.sleep(config['fail_sleep'])

if __name__ == '__main__':
    asyncio.run(main())
    