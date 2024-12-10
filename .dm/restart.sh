#!/bin/bash

# Restart the specified service based on the branch
# Usage: ./restart.sh branch

if [ -z "$1" ]; then
    echo "Error: No branch specified."
    echo "Usage: ./restart.sh branch"
    exit 1
fi

branch=$1

if [ "$branch" == "main" ]; then
    service_name="mielenosoitukset_fi"
else
    service_name="mielenosoitukset_fi_dev"
fi

if sudo systemctl restart "$service_name"; then
    echo "Service $service_name restarted successfully."
else
    echo "Error: Failed to restart $service_name."
    exit 1
fi