import boto3
import random

# Config
bucket = "ai-conversation-frontend"
outputs_prefix = "outputs/"
table_name = "ai-conversation-play"  # Extracted from the ARN
region = "us-east-1"                 # Extracted from the ARN

# AWS clients/resources
dynamodb = boto3.resource('dynamodb', region_name=region)
table = dynamodb.Table(table_name)
s3 = boto3.client('s3')

def dynamo_table_empty():
    response = table.scan(Limit=1)
    return 'Items' not in response or len(response['Items']) == 0

def list_s3_folders(prefix):
    paginator = s3.get_paginator('list_objects_v2')
    folders = set()
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter='/'):
        if 'CommonPrefixes' in page:
            for cp in page['CommonPrefixes']:
                # Remove prefix and trailing slashes for folder name
                folder = cp['Prefix'][len(prefix):].strip('/')
                if folder:
                    folders.add(folder)
    return list(folders)

def populate_dynamo_with_s3_folders():
    folders = list_s3_folders(outputs_prefix)
    print(f"Putting {len(folders)} folders in DynamoDB...")
    with table.batch_writer() as batch:
        for folder in folders:
            batch.put_item(Item={'id': folder})

def get_random_id_and_delete():
    # DynamoDB scan to get all IDs. (For large tables, use pagination!)
    all_items = []
    response = table.scan(ProjectionExpression='id')
    all_items.extend(response.get('Items', []))
    # If table is big, we should handle pagination (not needed here)
    
    if not all_items:
        print("No ids found in DynamoDB table.")
        return None

    chosen = random.choice(all_items)
    chosen_id = chosen['id']
    table.delete_item(Key={'id': chosen_id})
    return chosen_id

def lambda_handler(event, context):
    if dynamo_table_empty():
        populate_dynamo_with_s3_folders()
    chosen_id = get_random_id_and_delete()
    print(f"id: {chosen_id}")
    return {'id': chosen_id}

if __name__ == "__main__":
    print(lambda_handler({}, {}))