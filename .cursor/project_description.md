This is a project that aims to monitor and assist with debugging a Honeywell heating system.

This should be a multithreaded program that consists of the following parts:
1) A watcher that consumes messages from the USB interface using the ramses library 
   and pushes the messages to an internal python queue. Every message should be logged in the raw 
   to /home/simon/src/development/honeywell-radio-exporter/logs/raw_messages with python logging
   retaining 100mb of logs across 5 files. 
2) A consumer that updates a mysql database as messages come in.
3) A janitor thread that cleans up the database messages over 24 hours old and devices that haven't been seen in 4 weeks.

The database schema should include tables that at least cover:
1) devices - seen devices, not every column will be appropriate for ever device. This table with columns including; id, name, zone, type, last seen, messages to, messages from, setpoint, temperature.
2) messages - seen messages, types, payloads etc

We should have an exhaustive list of messages built up, preferably in a seperate validator.py. Every message should go through there. If we can't accurately validate a message we should log it so that we can improve the validator. Our goal is to ensure messages are correctly understood and processed.

The spec is https://github.com/ramses-rf/ramses_protocol

The application should expose a web endpoint including at least two endpoint;
/metrics/ prometheus consumable endpoints
/ui/ (redirected from /) ; a website for humans to see the current status

Key considerations include;
- Devices may not have names or it may take several messages to build up a full profile of a database.
- The database is our persistence layer, the UI and metrics should build up from it on application start
- The application should apply it's database schema on start up (credentials in .mysql_creds)
- The database server is a mysql host
- logs should be in /home/simon/src/development/honeywell-radio-exporter/logs/messages.log

