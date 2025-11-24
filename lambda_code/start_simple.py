import json
import boto3
import logging
import random

logging.basicConfig(format='[%(asctime)s] {%(filename)s:%(lineno)d} %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')
bucket = 'ai-conversation-frontend'

def get_inputs():
  inputs = []
  response = s3_client.list_objects_v2(Bucket=bucket, Prefix="inputs/")

  inputs = [obj['Key'] for obj in response.get('Contents', []) if not obj['Key'].endswith('/')]

  return inputs, len(inputs)

def get_uploads():
  inputs = []
  response = s3_client.list_objects_v2(Bucket=bucket, Prefix="uploads/")

  inputs = [obj['Key'] for obj in response.get('Contents', []) if not obj['Key'].endswith('/')]

  return inputs, len(inputs)

def get_random_input_and_clean(inputs, inputs_count):
  if inputs_count == 0:
    return None
  key = random.choice(inputs)

  response = s3_client.get_object(Bucket=bucket, Key=key)
  body = response['Body'].read().decode('utf-8').strip()

  s3_client.delete_object(Bucket=bucket, Key=key)
  return body

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
  
  random_input = get_random_input_and_clean(inputs, inputs_count)
  logger.info(f"Random input: {random_input}")

  if inputs_count <= 1:
    uploads, uploads_count = get_uploads()
    logger.info(f"Uploads count: {uploads_count}")
    force_new_uploads(uploads, uploads_count)
  
  return {'Topic': random_input, 'StartSpeaker': get_random_start_speaker()}  

if __name__ == "__main__":
  event = {  
   
}
  context = None
  print(lambda_handler(event, context))