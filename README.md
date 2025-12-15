# TWS monitoring
Interactive Brokers TWS monitoring service
## Installation
* Clone the repo:
```
git clone https://github.com/format37/tws_monitoring.git
cd tws_monitoring
nano .env
```
* Define .env:
```
BOT_TOKEN=YourBotToken
CHAT_ID=YourChatID
```
* TWS connection settings are configured in docker-compose.yml for each monitoring service (tws_monitoring_dnk, tws_monitoring_oleg):
```
  - `TWS_HOST` - TWS API host address
  - `TWS_PORT` - TWS API port
  - `TWS_CLIENT_ID` - Client ID for TWS connection
  - `CONTAINER_NAME` - Container identifier for notifications
```
* Provide run access
```
sudo chmod +x compose.sh
sudo chmod +x logs.sh
sudo chmod +x update.sh
```
* Run
```
./compose.sh
```