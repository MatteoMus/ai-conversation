# ai-conversation
Serverless AI conversation

## ai-conversation-frontend
aws cloudformation create-stack \
--stack-name ai-conversation-frontend \
--template-body file://cloudformation-frontend.yaml \
--capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
--region us-east-1

aws cloudformation create-change-set \
--stack-name ai-conversation-frontend \
--template-body file://cloudformation-frontend.yaml \
--capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
--region us-east-1 \
--change-set-name update