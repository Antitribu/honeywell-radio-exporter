This is a python project and everything should be written in python.

It will only ever run on linux.

When files are changed the program will reload if it's running in dev mode

## Graceful shutdown

To stop the exporter cleanly, call the HTTP endpoint:

`GET /graceful_shutdown`

The server will signal the background consumer/janitor/watchers to stop and then exit.
In `dev` mode (`scripts/dev.sh`), the exited process will be restarted automatically.
