import boto3
import logging

# Initialize the API Gateway client
apigateway_client = boto3.client('apigateway')
cloudfront_client = boto3.client('cloudfront')
distribution_id = 'EJTPZSTF964T0'
api_key_name = 'ai-conversation-api-key'

logging.basicConfig(format='[%(asctime)s] {%(filename)s:%(lineno)d} %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Find the API key ID by name
def get_api_key_id_by_name(name):
  paginator = apigateway_client.get_paginator('get_api_keys')
  for page in paginator.paginate():
    for api_key in page['items']:
      if api_key['name'] == name:
        return api_key['id']
  return None

def on_off_api_key(action):
  api_key_id = get_api_key_id_by_name(api_key_name)

  if api_key_id:
    # Disable the API key
    apigateway_client.update_api_key(
      apiKey=api_key_id,
      patchOperations=[
      {
        'op': 'replace',
        'path': '/enabled',
        'value': 'true' if action == 'on' else 'false'
      }
      ]
    )
    logger.info(f"API key '{api_key_name}' has been {'enabled' if action == 'on' else 'disabled'}.")
  else:
    logger.info(f"API key '{api_key_name}' not found.")

def on_off_cloudfront(action):
  # Get the current distribution config and ETag
  response = cloudfront_client.get_distribution_config(Id=distribution_id)
  config = response['DistributionConfig']
  etag = response['ETag']

  # Set the Enabled field based on action
  config['Enabled'] = True if action == 'on' else False

  # Update the distribution
  cloudfront_client.update_distribution(
    DistributionConfig=config,
    Id=distribution_id,
    IfMatch=etag
  )
  logger.info(f"CloudFront distribution '{distribution_id}' has been {'enabled' if action == 'on' else 'disabled'}.")

def lambda_handler(event, context):
  logger.info(f"Event: {event}")
  action = event.get('action', 'off').lower()
  
  #on_off_api_key(action)
  on_off_cloudfront(action)

if __name__ == "__main__":
  event = {"action": "on"}
  context = None
  print(lambda_handler(event, context))