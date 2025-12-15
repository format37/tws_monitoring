source .env
sudo docker rm -fv tws_monitoring_dnk || true
sudo docker rm -fv tws_monitoring_oleg || true
sudo docker compose up --build --remove-orphans -d --force-recreate tws_monitoring_dnk tws_monitoring_oleg