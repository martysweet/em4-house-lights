#!/bin/sh

cd src/response_handler
pip install requests -t .
cd ../..

cd src/alexa
pip install requests -t .
pip install python-jose -t .
cd ../..

sam package \
    --template-file template.yaml \
    --output-template-file serverless-output.yaml \
    --s3-bucket msweet-deployment-artifacts \
    --profile martysweet-marty

sam deploy \
    --template-file serverless-output.yaml \
    --stack-name house-lighting-development \
    --capabilities CAPABILITY_IAM \
    --profile martysweet-marty