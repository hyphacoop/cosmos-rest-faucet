FROM python:3.8-alpine
WORKDIR /app
RUN apk add make go git
RUN git clone https://github.com/noble-assets/noble.git
RUN cd noble && git checkout v4.1.0-rc.1 && LEDGER_ENABLED=false make install
RUN cp /root/go/bin/nobled /usr/local/bin/
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD [ "hypercorn", "-b" , "0.0.0.0:8000", "cosmos_rest_faucet:app"]
