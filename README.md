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
TWS_CLIENT_ID=10
CONTAINER_NAME=tws_monitoring
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