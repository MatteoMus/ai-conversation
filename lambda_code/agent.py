import json
import boto3
import logging

logging.basicConfig(format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')
polly_client = boto3.client('polly')
s3_client = boto3.client('s3')

def speaker(input: str, agent: dict, conversation_params: dict) -> str:
    agentResponse = bedrock_agent_runtime_client.invoke_agent(
        inputText=input,
        agentId=agent['agentId'],
        agentAliasId=agent['agentAliasId'],
        sessionId=conversation_params['session_id'],
        enableTrace=conversation_params['enable_trace'], 
        endSession=conversation_params['end_session']
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

def synthesize(body: str, voice: str, audio_name: str):
    response = polly_client.synthesize_speech(
        Text=body,
        OutputFormat='mp3',
        VoiceId=voice
    )
    print(f"Response: {response}")
    filename = f"/tmp/{audio_name}"

    if 'AudioStream' in response:
        with open(filename, 'wb') as file:
            file.write(response['AudioStream'].read())        
        return filename
    else:
        raise Exception("Could not synthesize speech from text.")

def push_s3(filename: str, bucket: str, audio_name: str, UUID: str):
    with open(filename, 'rb') as data:
        s3_client.upload_fileobj(data, bucket, f"{UUID}/{audio_name}")

def lambda_handler(event, context):

    audio_name = str(event['Turn']) + ".mp3"
    response_text = speaker(event['Input'], event['Speaker'], event['ConversationParams'])
    response_audio = synthesize(response_text, event['Speaker']['voice'], audio_name)
    push_s3(response_audio, 'ai-conversation-matteo-mus-eu-west-1-992382403092', audio_name, event['UUID'])
    return json.dumps(response_text)