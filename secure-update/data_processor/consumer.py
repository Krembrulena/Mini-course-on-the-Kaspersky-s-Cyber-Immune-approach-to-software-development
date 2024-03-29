# implements Kafka topic consumer functionality

from email.mime import base
import threading
from confluent_kafka import Consumer, OFFSET_BEGINNING
import json
from producer import proceed_to_deliver
from urllib.request import urlopen
import base64

RHUMIDITY_THRESHOLD = 65
TEMPERATURE_THRESHOLD = 15
PRESSURE_THRESHOLD = 108640

def check_new_data(data:list, details):
    details["alerts"] = []
    for sample in data:
        if "param_name" in sample:
            if sample["param_name"] == "RHumidity":
                rhumidity = sample["param_value"]
                if rhumidity > RHUMIDITY_THRESHOLD:
                    details["alerts"].append(
                        {
                            "source_id": details["id"],
                            "event": "overhumidity",
                            "rhumidity_value": rhumidity,
                            "rhumidity_threshold": RHUMIDITY_THRESHOLD
                        }
                    )
            elif sample["param_name"] == "Temperature":
                temperature = sample["param_value"]
                if temperature > TEMPERATURE_THRESHOLD:
                    details["alerts"].append(
                        {
                            "source_id": details["id"],
                            "event": "overheating",
                            "temperature_value": temperature,
                            "temperature_threshold": TEMPERATURE_THRESHOLD
                        }
                    )
            elif sample["param_name"] == "Pressure":
                pressure = sample["param_value"]
                if pressure > PRESSURE_THRESHOLD:
                    details["alerts"].append(
                        {
                            "source_id": details["id"],
                            "event": "overload",
                            "pressure_value": pressure,
                            "pressure_threshold": PRESSURE_THRESHOLD
                        }
                    )

def handle_event(id: str, details: dict):    
    # print(f"[debug] handling event {id}, {details}")
    print(f"[info] handling event {id}, {details['source']}->{details['deliver_to']}: {details['operation']}")
    try:
        if details['operation'] == 'process_new_data':
            new_data = details['new_data']
            check_new_data(new_data, details)
            if len(details["alerts"]) > 0:
                details['deliver_to'] = 'data_output'
                details['operation'] = 'process_new_events'
                proceed_to_deliver(id, details)
    except Exception as e:
        print(f"[error] failed to handle request: {e}")

def consumer_job(args, config):
    # Create Consumer instance
    downloader_consumer = Consumer(config)

    # Set up a callback to handle the '--reset' flag.
    def reset_offset(downloader_consumer, partitions):
        if args.reset:
            for p in partitions:
                p.offset = OFFSET_BEGINNING
            downloader_consumer.assign(partitions)

    # Subscribe to topic
    topic = "data_processor"
    downloader_consumer.subscribe([topic], on_assign=reset_offset)

    # Poll for new messages from Kafka and print them.
    try:
        while True:
            msg = downloader_consumer.poll(1.0)
            if msg is None:
                # Initial message consumption may take up to
                # `session.timeout.ms` for the consumer group to
                # rebalance and start consuming
                # print("Waiting...")
                pass
            elif msg.error():
                print(f"[error] {msg.error()}")
            else:
                # Extract the (optional) key and value, and print.
                try:
                    id = msg.key().decode('utf-8')
                    details_str = msg.value().decode('utf-8')
                    # print("[debug] consumed event from topic {topic}: key = {key:12} value = {value:12}".format(
                        # topic=msg.topic(), key=id, value=details_str))
                    handle_event(id, json.loads(details_str))
                except Exception as e:
                    print(
                        f"Malformed event received from topic {topic}: {msg.value()}. {e}")
    except KeyboardInterrupt:
        pass
    finally:
        # Leave group and commit final offsets
        downloader_consumer.close()


def start_consumer(args, config):
    threading.Thread(target=lambda: consumer_job(args, config)).start()

