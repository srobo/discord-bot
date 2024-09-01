FROM python:3.9-slim-bullseye

WORKDIR /usr/src/app

COPY . .
RUN pip install --no-cache-dir .

CMD [ "python", "-m", "sr.discord_bot" ]
