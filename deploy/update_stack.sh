#!/bin/bash
STACK=$1
IMAGE=$2
aws cloudformation update-stack --stack-name $STACK --use-previous-template --parameters \
        ParameterKey="ContVersion",ParameterValue="$IMAGE" \
        ParameterKey="VpcId",UsePreviousValue=true \
        ParameterKey="InstanceType",UsePreviousValue=true \
        ParameterKey="SubnetID",UsePreviousValue=true \
        ParameterKey="KeyName",UsePreviousValue=true \
        ParameterKey="MaxSize",UsePreviousValue=true \
        ParameterKey="LocalBroker",UsePreviousValue=true \
        ParameterKey="MongoURI",UsePreviousValue=true \
        ParameterKey="TelegramEndpoint",UsePreviousValue=true \
        --capabilities CAPABILITY_NAMED_IAM --region eu-west-1