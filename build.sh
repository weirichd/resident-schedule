#!/usr/bin/env bash
if [ $# -eq 0 ]
  then
    tag='latest'
  else
    tag=$1
fi

echo -e "\e[1m\e[34mBuilding Docker Image... \e[0m"

docker build -t weirich.david/resident_schedule:$tag .

echo -e "\e[1m\e[34mCreating ZIP Archive... \e[0m"
rm app.zip && zip -r app.zip *
