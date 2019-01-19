

https://github.com/cloudtools/gghelper/releases/download/0.0.2/gghelper_linux

# Creating the group
./gghelper creategroup -name Lighting 
- Deploy certificates to GGCore
./gghelper lambda -pinned -d src -handler index.lambda_handler -name LightingController -role lambda_basic_execution -runtime python2.7 
./gghelper createsub -source cloud -target LightingController -subject "lighting/request" 
./gghelper createsub -source LightingController -target cloud -subject "lighting/response" 
./gghelper createdeployment 

# Install GGCore
```
sudo adduser --system ggc_user
sudo addgroup --system ggc_group
```