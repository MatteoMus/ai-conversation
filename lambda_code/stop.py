import json
import boto3
import logging
import re

logging.basicConfig(format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s', level=logging.ERROR)
logger = logging.getLogger(__name__)
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')
s3_client = boto3.client('s3')

def agent(input: str, agent: dict, conversation_params: dict) -> str:
    agentResponse = bedrock_agent_runtime_client.invoke_agent(
        inputText=input,
        agentId=agent['agentId'],
        agentAliasId=agent['agentAliasId'],
        sessionId=conversation_params['session_id'],
        enableTrace=conversation_params['enable_trace'], 
        endSession=conversation_params['end_session']
    )
    logger.error(f"AGENT RESPONSE: {agentResponse}")

    event_stream = agentResponse['completion']
    agent_answer = ""
    try:
        for event in event_stream:        
            if 'chunk' in event:
                data = event['chunk']['bytes']
                agent_answer += data.decode('utf8')  # Accumulate response chunks
            elif 'trace' in event:
                logger.info(json.dumps(event['trace'], indent=2))
            else:
                raise Exception("Unexpected event.", event)
    except Exception as e:
        raise Exception("Unexpected event.", e)

    return agent_answer.strip()

def get_stop_from_tags(input_str):
    # Define the regex pattern to match content inside <STOP> and </STOP> tags
    pattern = r"<STOP>(.*?)</STOP>"
    match = re.search(pattern, input_str, re.IGNORECASE)
    if match:
        # Extract the content inside the tags
        content = match.group(1).strip().lower()
        # Return True if the content is "true", otherwise False
        return content == "true"
    else:
        # Raise an error if <STOP> tags are not found
        raise ValueError("Input does not contain valid <STOP> tags.")

def text_push_s3(body: str, bucket: str, text_name: str, UUID: str):
    s3_client.put_object(Body=body, Bucket=bucket, Key=f"outputs/{UUID}/{text_name}")

def extract_reasoning(text: str) -> str:
    # Try to find reasoning tag
    reasoning_match = re.search(r'<reasoning>(.*?)</reasoning>', text, re.DOTALL)
    if reasoning_match:
        return reasoning_match.group(1).strip()
    
    # If no reasoning tag, extract everything outside <STOP>...</STOP>
    outside_text = re.sub(r'<STOP>.*?</STOP>', '', text, flags=re.DOTALL).strip()
    return outside_text

def lambda_handler(event, context):
    #print input
    logger.error(f"EVENT: {event}")

    #vars
    s3_bucket_name = 'ai-conversation-matteo-mus-eu-west-1-992382403092'
    s3_folder_name = f"outputs/{event['UUID']}"
    max_retries = 2  # Maximum number of retries for agent response generation
    retry_attempts = 0
    response_text = None
    full_conversation = event['ConversationHistory']

    #evaluate minimum number of turns
    if int(event['Turn']) < 3:
        logger.error("Number of turn under minimun required")
        return {
            "stop": False,
            "reasoning": f"<reasoning></reasoning>"
        }

    #get conversation history
    conversation_history = f"<conversation_history>{full_conversation}</conversation_history>"
    logger.error(conversation_history)
    
    # Retry logic for agent response generation
    while retry_attempts < max_retries:
        try:
            # Generate agent response
            response_text = agent(conversation_history, event['Stop'], event['ConversationParams'])
            logger.error(f"RESPONSE TEXT ATTEMPT #{retry_attempts}: {response_text}")

            # Check and return stop condition
            stop = get_stop_from_tags(response_text)

            #get reasoning
            reasoning = extract_reasoning(response_text)
            
            return {
                "stop": stop,
                "reasoning": f"<reasoning>{reasoning}</reasoning>"
            }
        except ValueError as ve:
            # Handle missing <STOP> tags specifically
            retry_attempts += 1
            logger.error(f"<STOP> tag extraction failed (attempt #{retry_attempts}): {ve}")
        except Exception as e:
            # Handle other agent-related errors
            retry_attempts += 1
            logger.error(f"Agent failed (attempt #{retry_attempts}): {e}")

    # If reached, agent generation failed after retries
    logger.error("Max retries reached while attempting to generate a valid response.")
    return {
        "stop": False,
        "reasoning": f"<reasoning></reasoning>"
    }