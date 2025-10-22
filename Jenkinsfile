pipeline {
    agent any

    environment {
        // 🚨 FIX: Updated region to match the active EC2 instance
        AWS_REGION = 'eu-north-1'
        ECR_REPO   = 'weather-dashboard'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Get AWS Account') {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                                     usernameVariable: 'AWS_ACCESS_KEY_ID',
                                                     passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                        def acct = powershell(
                            returnStdout: true,
                            script: '''
                                $env:AWS_ACCESS_KEY_ID = "${AWS_ACCESS_KEY_ID}"
                                $env:AWS_SECRET_ACCESS_KEY = "${AWS_SECRET_ACCESS_KEY}"
                                aws sts get-caller-identity --query Account --output text
                            '''
                        ).trim()
                        if (!acct) { error "Failed to get AWS account ID" }
                        env.AWS_ACCOUNT_ID = acct
                        echo "AWS account: ${env.AWS_ACCOUNT_ID}"
                    }
                }
            }
        }

        stage('Login to ECR (diagnose)') {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                                     usernameVariable: 'AWS_ACCESS_KEY_ID',
                                                     passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                        bat """
                            REM Set environment variables for AWS CLI
                            set AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
                            set AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
                            set AWS_REGION=${AWS_REGION}
                            set AWS_ACCOUNT_ID=${env.AWS_ACCOUNT_ID}

                            echo AWS account: %AWS_ACCOUNT_ID%
                            set ECR_URI=%AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com
                            echo ECR URI: %ECR_URI%

                            REM Get ECR Login Token
                            FOR /F "tokens=*" %%i IN ('aws ecr get-login-password --region %AWS_REGION% --output text --no-cli-pager') DO (
                                SET AWS_TOKEN=%%i
                            )
                            
                            echo %AWS_TOKEN% | docker login --username AWS --password-stdin %ECR_URI%

                            IF NOT ERRORLEVEL 0 (
                                echo Docker login failed.
                                exit /b 5
                            )

                            echo Docker login succeeded.
                        """
                    }
                }
            }
        }

        stage('Build image') {
            steps {
                powershell """
                    if (-not \$env:ECR_REPO) { Write-Error "ECR_REPO not set"; exit 1 }
                    
                    \$tag = "\$env:BUILD_NUMBER" 

                    Write-Output "Building Docker image \$tag"
                    docker build -t \$tag -f Dockerfile .
                    if (\$LASTEXITCODE -ne 0) { Write-Error "Docker build failed"; exit 1 }
                """
            }
        }

        stage('Tag & Push to ECR') {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                                     usernameVariable: 'AWS_ACCESS_KEY_ID',
                                                     passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                        bat """
                            REM Set environment variables for AWS CLI
                            set AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
                            set AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
                            set AWS_REGION=${AWS_REGION}
                            set AWS_ACCOUNT_ID=${env.AWS_ACCOUNT_ID}

                            REM Re-run ECR login for push
                            set ECR_URI_AUTH=%AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com
                            
                            REM Use FOR /F to capture the clean token
                            FOR /F "tokens=*" %%i IN ('aws ecr get-login-password --region %AWS_REGION% --output text --no-cli-pager') DO (
                                SET AWS_TOKEN=%%i
                            )
                            
                            echo %AWS_TOKEN% | docker login --username AWS --password-stdin %ECR_URI_AUTH%
                            
                            IF NOT ERRORLEVEL 0 (
                                echo Docker login failed before push.
                                exit /b 5
                            )
                            
                            REM Define tags based on the full repo name
                            set LOCAL_REPO_NAME=%ECR_REPO%
                            set ECR_URI_FULL=%AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/%LOCAL_REPO_NAME%
                            
                            set LOCAL_TAG=%BUILD_NUMBER% 
                            set REMOTE_TAG=%ECR_URI_FULL%:%BUILD_NUMBER%

                            echo Tagging image...
                            docker tag %LOCAL_TAG% %REMOTE_TAG%
                            IF NOT ERRORLEVEL 0 (
                                echo Docker tag failed!
                                exit /b 1
                            )

                            echo Pushing %REMOTE_TAG%
                            docker push %REMOTE_TAG%
                            IF NOT ERRORLEVEL 0 (
                                echo Docker push failed.
                                exit /b 1
                            )

                            REM Write ECR info to file
                            echo ECR_URI=%REMOTE_TAG%> ecr_info.txt
                        """
                    }
                }
            }
            post { success { archiveArtifacts artifacts: 'ecr_info.txt' } }
        }

        stage('Resolve EC2 IP (by tag)') {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                                     usernameVariable: 'AWS_ACCESS_KEY_ID',
                                                     passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                        bat """
                            @echo off
                            REM Set environment variables for AWS CLI
                            set AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
                            set AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
                            set AWS_REGION=${AWS_REGION}
                            set EC2_HOST_TEMP_FILE=ec2_host_ip.txt
                            
                            echo Searching for running EC2 instance in %AWS_REGION% with tag Name=weather-new...

                            REM Query AWS CLI and write ONLY the IP to the temp file
                            aws ec2 describe-instances --region %AWS_REGION% --filters "Name=tag:Name,Values=weather-new" "Name=instance-state-name,Values=running" --query "Reservations[0].Instances[0].PublicIpAddress" --output text > %EC2_HOST_TEMP_FILE%

                            REM Read the IP from the file and store it in an environment variable (for logging/checking)
                            SET /P EC2_IP=< %EC2_HOST_TEMP_FILE%

                            IF NOT DEFINED EC2_IP GOTO IP_ERROR
                            IF "%EC2_IP%" == "None" GOTO IP_ERROR

                            echo Resolved EC2 Host IP: %EC2_IP%
                            GOTO END

                            :IP_ERROR
                            echo ERROR: Could not find running EC2 (tag Name=weather-new) in %AWS_REGION%. Check instance status.
                            exit /b 1

                            :END
                        """
                        // Read the IP (which is the only content of the file) and assign it to the environment variable.
                        // Note: The file name has been changed to ec2_host_ip.txt to avoid confusion with the old variable name
                        def ip = readFile('ec2_host_ip.txt').trim()
                        env.EC2_HOST = ip.trim()
                        echo "EC2_HOST set to: ${env.EC2_HOST}"
                        // clean up temp file
                        bat 'del /f ec2_host_ip.txt'
                    }
                }
            }
        }

        stage('Deploy to EC2') {
    steps {
        script {
            // Pre-resolve Groovy environment variables for use in the bat command
            def ec2Host = env.EC2_HOST 
            def awsRegion = env.AWS_REGION

            // 1. Resolve SSH_KEY_PATH within the withCredentials block
            withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh', keyFileVariable: 'SSH_KEY_PATH')]) {
                def keyPath = env.SSH_KEY_PATH
                
                // Add this step to ensure line endings are correct before SCP
                // NOTE: The 'dos2unix' tool must be installed and in the PATH on the Windows Jenkins agent
                bat 'dos2unix deploy.sh'

                // 2. Execute the deployment script
                bat """
                    @echo off

                    REM --- 1. Fix Key Permissions (KeyPath is Groovy-interpolated) ---
                    echo Securing private key file: ${keyPath}
                    icacls "${keyPath}" /inheritance:r
                    icacls "${keyPath}" /grant:r "NT AUTHORITY\\SYSTEM":F
                    icacls "${keyPath}" /grant:r "Administrators":F
                    
                    IF ERRORLEVEL 1 (
                        echo ERROR: Failed to set secure permissions on the SSH key.
                        exit /b 1
                    )
                    
                    REM --- 2. Deployment Logic ---
                    
                    REM Retrieve ECR URI from the artifact file
                    set /p ECR_URI_RAW=<ecr_info.txt
                    REM Set the temporary Batch variable ECR_URI_CLEAN
                    set ECR_URI_CLEAN=%%ECR_URI_RAW:ECR_URI=%%

                    REM Check EC2_HOST (Groovy-interpolated)
                    IF "${ec2Host}"=="" (
                        echo ERROR: EC2_HOST is not set. Deployment aborted.
                        exit /b 1
                    )

                    echo Copying deploy.sh to ubuntu@${ec2Host}
                    
                    REM SCP command (Groovy-interpolated variables: keyPath, ec2Host)
                    scp -o StrictHostKeyChecking=no -i "${keyPath}" .\\deploy.sh ubuntu@${ec2Host}:/home/ubuntu/deploy.sh
                    
                    IF NOT ERRORLEVEL 0 (
                        echo SCP failed!
                        exit /b 1
                    )

                    REM Use immediate Batch expansion for ECR_URI_CLEAN for the echo line
                    echo Running deploy on ${ec2Host} with image %ECR_URI_CLEAN%
                    
                    REM SSH command
                    REM keyPath, ec2Host, awsRegion are Groovy-interpolated.
                    REM ECR_URI_CLEAN uses **single percent signs** for immediate Batch expansion on the command line.
                    ssh -o StrictHostKeyChecking=no -i "${keyPath}" ubuntu@${ec2Host} "bash /home/ubuntu/deploy.sh %ECR_URI_CLEAN% ${awsRegion}"
                    
                    IF NOT ERRORLEVEL 0 (
                        echo SSH deployment failed!
                        exit /b 1
                    )
                    
                    echo Deployment successful to ${ec2Host}.
                """
            }
        }
    }
}
    }
}