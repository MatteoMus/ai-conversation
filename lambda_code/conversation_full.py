import json
import boto3
import logging
import re

logging.basicConfig(format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s', level=logging.ERROR)
logger = logging.getLogger(__name__)
s3_client = boto3.client('s3')

def get_conversation_history(s3_bucket_name, s3_folder_name):

    # Initialize an empty string to hold the concatenated content
    all_content = ""

    # List objects in the specified bucket and folder
    response = s3_client.list_objects_v2(Bucket=s3_bucket_name, Prefix=s3_folder_name)

    if 'Contents' in response:
        # Loop through all files in the folder
        for obj in response['Contents']:
            file_key = obj['Key']
            # Check if the file has a .txt extension
            if file_key.endswith('.txt') and file_key != f"{s3_folder_name}/full_conversation.txt":
                # Fetch the file content
                file_obj = s3_client.get_object(Bucket=s3_bucket_name, Key=file_key)
                file_content = file_obj['Body'].read().decode('utf-8')
                # Remove XML tags using a regular expression
                file_content_no_tags = re.sub(r'<[^>]*>', '', file_content)
                # Append content to the variable
                all_content += file_content_no_tags.strip() + "\n--------------------\n"  # Add a separator between files
    else:
        print("No files found in the folder.")

    return all_content

def text_push_s3(body: str, bucket: str, text_name: str, UUID: str):
    s3_client.put_object(Body=body, Bucket=bucket, Key=f"outputs/{UUID}/{text_name}")

def lambda_handler(event, context):
    #print input
    logger.error(f"EVENT: {event}")

    #vars
    s3_bucket_name = 'ai-conversation-matteo-mus-eu-west-1-992382403092'
    s3_folder_name = f"outputs/{event['UUID']}"

    #get conversation history
    full_conversation = get_conversation_history(s3_bucket_name, s3_folder_name)
    text_push_s3(full_conversation, s3_bucket_name, 'full_conversation.txt', event['UUID'])
    
    return full_conversation