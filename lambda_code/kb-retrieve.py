import json
import boto3
import logging
import re


logging.basicConfig(format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')

def retrieve_knowledge(knowledge_base_id, query):
    try:
      response = bedrock_agent_runtime_client.retrieve(
          knowledgeBaseId=knowledge_base_id,
          retrievalQuery={
            'text': query
          },
          retrievalConfiguration={
              "vectorSearchConfiguration": {
                "numberOfResults": 5    
              }
              
          }
      )
      logger.info(f"Retrived knowledge: {response}")
      texts = [item["content"]["text"] for item in response["retrievalResults"]]
      all_text = "\n\n".join(texts)

      return all_text
    except Exception as e:
      logger.info(f"Error retrieving knowledge: {e}")
      return "Error retrieving knowledge"

def generate( input: str, agent: dict, conversation_params: dict, knowledge: str):
    agentResponse = bedrock_agent_runtime_client.invoke_agent(
        inputText=input,
        agentId=agent['agentId'],
        agentAliasId=agent['agentAliasId'],
        sessionId=conversation_params['session_id'],
        enableTrace=conversation_params['enable_trace'], 
        endSession=conversation_params['end_session'],
        sessionState={
            "promptSessionAttributes": {
                "context": knowledge
            }
        }
    )
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


def lambda_handler(event, context):
    logger.info(f"EVENT: {event}")
    knowledge_base_id = event['knowledge_base_id']
    input = event['input']
    agent = event['agent'] 
    conversation_params = event['conversation_params']
    
    knowledge = retrieve_knowledge(knowledge_base_id, input)
    logger.info(f"knowledge: {knowledge}")

    response = generate(input, agent, conversation_params, knowledge)
    print(f"Response: {response}")
    return {
        'statusCode': 200,
        'body': json.dumps(response)
    }

if __name__ == "__main__":
  import uuid
  # Simulate an event for local testing
  event = { 
      'knowledge_base_id': 'Y1HLBKNOOY',
      'input': f"""talk about prostitution
""",
      'agent': { 'agentId': 'MMEMV3D00P', 'agentAliasId': 'DV1VR4HFSO' },
      'conversation_params': { 'session_id': str(uuid.uuid4()), 'enable_trace': False, 'end_session': False } 
  }
  context = None
  result = lambda_handler(event, context)
