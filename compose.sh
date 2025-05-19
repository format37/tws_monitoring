source .env

# Break if $CONTAINER_NAME is not set
if [ -z "$CONTAINER_NAME" ]; then
    echo "CONTAINER_NAME is not set"
    exit 1
else
    echo "CONTAINER_NAME is set to $CONTAINER_NAME"
fi

# Notify and exit if data/config.json is not present
if [ ! -f "data/config.json" ]; then
    echo "Error: data/config.json is not present"
    exit 1
fi

# sudo docker compose down -v
# sudo docker compose up --build --force-recreate --remove-orphans -d

sudo docker rm -fv "$CONTAINER_NAME" || true
sudo docker compose up --build --remove-orphans -d --force-recreate $CONTAINER_NAME