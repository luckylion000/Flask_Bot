#!/bin/bash
STACK=$1
TAG=$2
aws cloudformation get-template --stack-name $STACK | jq .TemplateBody --raw-output --sort-keys > template.json
aws cloudformation deploy --template-file template.json --stack-name $STACK --parameter-overrides ContVersion=$TAG --capabilities CAPABILITY_NAMED_IAM --region eu-west-1
#rm template.json