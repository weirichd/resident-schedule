FROM python:3

MAINTAINER David E. Weirich "weirich.david@gmail.com"

COPY . /app

WORKDIR /app

EXPOSE 5000

ENTRYPOINT [ "python" ]

CMD [ "app.py" ]

