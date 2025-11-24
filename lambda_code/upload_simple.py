import json
import boto3
import logging
import io
import hashlib

logging.basicConfig(format='[%(asctime)s] {%(filename)s:%(lineno)d} %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')
bucket = 'ai-conversation-frontend'
dst_prefix = 'inputs/'

def lambda_handler(event, context):
  logger.info(f"Event: {event}")
  src_key = event['Records'][0]['s3']['object']['key']
  obj = s3_client.get_object(Bucket=bucket, Key=src_key)
  body = obj['Body'].read().decode('utf-8')

  # Process and upload
  for idx, line in enumerate(body.splitlines(), start=1):
      content = line.strip()
      if content:
          s3_key = f"{dst_prefix}{hashlib.md5(content.encode('utf-8')).hexdigest()}.txt"
          fileobj = io.BytesIO(content.encode('utf-8'))
          s3_client.upload_fileobj(fileobj, bucket, s3_key)
          logger.info(f"Uploaded line {idx} to s3://{bucket}/{s3_key}")

  return {'statusCode': 200, 'body': json.dumps('File processed and uploaded successfully!')}  

if __name__ == "__main__":
  event = {  
   "Records":[  
      {  
         "s3":{  
            "object":{  
               "key":"uploads/test.txt"
            }
         }
      }
   ]
}
  context = None
  lambda_handler(event, context)