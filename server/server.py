import os
import logging
import requests
import time
import socket
import threading
import queue
import random
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TWSHealthCheck(EWrapper, EClient):
    def __init__(self, host, port):
        EClient.__init__(self, self)
        self.host = host
        self.port = port
        self.connected = False
        self.server_time = None
        self.exception_queue = queue.Queue()  # To collect thread exceptions

    def currentTime(self, time_from_server):
        """Callback when server time is received."""
        self.server_time = time_from_server
        logging.info(f"Server time received: {time.ctime(time_from_server)}")

    def error(self, req_id, error_code, error_string):
        """Callback for error handling."""
        # Ignore informational messages (2104, 2106, 2158)
        if error_code in [2104, 2106, 2158]:
            logging.debug(f"Informational: {error_code}: {error_string}")
            return
        logging.error(f"Error {error_code}: {error_string}")
        if error_code in [502, 504, 1100, 326]:  # Connection-related errors, including client ID conflict
            self.connected = False

    def connectAck(self):
        """Callback when connection is acknowledged."""
        self.connected = True
        logging.info("Connection established successfully.")

def run_client(app):
    """Run the EClient loop and capture exceptions."""
    try:
        app.run()
    except Exception as e:
        app.exception_queue.put(f"Client thread error: {str(e)}")
        logging.error(f"Client thread error: {str(e)}")

def check_tws_api_health(host="localhost", port=9999, timeout=5, client_id=10):
    """
    Check the health of the TWS API.
    Returns tuple of (is_healthy, status_message).
    """
    logging.info(f"Attempting to connect to TWS API at {host}:{port}...")
    app = TWSHealthCheck(host, port)
    client_thread = None

    try:
        # Connect to TWS API with a provided client ID
        app.connect(host, port, clientId=client_id)

        # Start the client loop in a separate thread
        client_thread = threading.Thread(target=run_client, args=(app,), daemon=True)
        client_thread.start()

        # Wait for connection acknowledgment or timeout
        start_time = time.time()
        while not app.connected and time.time() - start_time < timeout:
            time.sleep(0.1)

        if not app.connected:
            return False, "Failed to establish connection within timeout period."

        # Request current server time to verify API responsiveness
        app.reqCurrentTime()

        # Wait for server time response or timeout
        start_time = time.time()
        while app.server_time is None and time.time() - start_time < timeout:
            time.sleep(0.1)

        # Check for thread exceptions
        try:
            exception_msg = app.exception_queue.get_nowait()
            return False, exception_msg
        except queue.Empty:
            pass

        if app.server_time is None:
            return False, "Failed to receive server time response."

        return True, "TWS API is healthy and responsive."

    except socket.error as e:
        return False, f"Connection failed: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"
    finally:
        if app.isConnected():
            app.disconnect()
            logging.info("Disconnected from TWS API.")
        # Wait for client thread to exit
        if client_thread:
            time.sleep(0.2)  # Increased wait time for cleaner disconnection

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

def main():
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
            is_healthy, status_message = check_tws_api_health(
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
            time.sleep(sleep_time)

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
            time.sleep(config['fail_sleep'])

if __name__ == '__main__':
    main()
    