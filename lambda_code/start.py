import json
import boto3
import logging
import random
import botocore

logging.basicConfig(format='[%(asctime)s] {%(filename)s:%(lineno)d} %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')
bucket = 'ai-conversation-frontend'

def get_inputs():
  inputs = []
  response = s3_client.list_objects_v2(Bucket=bucket, Prefix="inputs/")

  inputs = [
        obj['Key'] for obj in response.get('Contents', [])
        if obj['Key'].endswith('.txt') and not obj['Key'].endswith('/')
    ]

  return inputs, len(inputs)

def get_uploads():
  inputs = []
  response = s3_client.list_objects_v2(Bucket=bucket, Prefix="uploads/")

  inputs = [obj['Key'] for obj in response.get('Contents', []) if not obj['Key'].endswith('/')]

  return inputs, len(inputs)

def get_random_input_and_clean(inputs, inputs_count, uuid):
  if inputs_count == 0:
    return None
  key = random.choice(inputs)

  response = s3_client.get_object(Bucket=bucket, Key=key)
  body = response['Body'].read().decode('utf-8').strip()

  push_topic_and_clean(key, uuid)

  #push_announce_and_clean(key.replace(".txt", ".mp3"), uuid)
  return body

def push_announce_and_clean(key, uuid):
    copy_source = {'Bucket': bucket, 'Key': key}
    dest_key = f"outputs/{uuid}/0.mp3"
    print(f"Attempting to copy {key} to {dest_key}")
    try:
        s3_client.copy_object(CopySource=copy_source, Bucket=bucket, Key=dest_key)
        s3_client.delete_object(Bucket=bucket, Key=key)
        print("Copy and delete successful")
    except botocore.exceptions.ClientError as e:
        print(f"Error copying {key}: {e}")

def push_topic_and_clean(key, uuid):
    copy_source = {'Bucket': bucket, 'Key': key}
    dest_key = f"outputs/{uuid}/topic.txt"
    print(f"Attempting to copy {key} to {dest_key}")
    try:
        s3_client.copy_object(CopySource=copy_source, Bucket=bucket, Key=dest_key)
        s3_client.delete_object(Bucket=bucket, Key=key)
        print("Copy and delete successful")
    except botocore.exceptions.ClientError as e:
        print(f"Error copying {key}: {e}")

def force_new_uploads(uploads, uploads_count):
  if uploads_count == 0:
    return None
  
  for key in uploads:
    response = s3_client.get_object(Bucket=bucket, Key=key)
    body = response['Body'].read()
    s3_client.put_object(Bucket=bucket, Key=key, Body=body)

  return 0

def get_random_start_speaker():
  speakers = ["Speaker1", "Speaker2",]
  return random.choice(speakers)

def lambda_handler(event, context):
  logger.info(f"Event: {event}")
  
  inputs, inputs_count = get_inputs()
  logger.info(f"Inputs count: {inputs_count}")
  
  random_input = get_random_input_and_clean(inputs, inputs_count, event["UUID"])
  logger.info(f"Random input: {random_input}")

  if inputs_count == 0:
    return {'Topic': None, 'StartSpeaker': get_random_start_speaker(), 'End': True}
  # if inputs_count <= 1:
  #   uploads, uploads_count = get_uploads()
  #   logger.info(f"Uploads count: {uploads_count}")
  #   force_new_uploads(uploads, uploads_count)
  
  return {'Topic': random_input, 'StartSpeaker': get_random_start_speaker(), 'End': False}  

if __name__ == "__main__":
  import uuid
  event = {  
   "UUID": str(uuid.uuid4())
}
  context = None
  print(lambda_handler(event, context))