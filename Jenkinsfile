pipeline {
    agent any

    environment {
        AWS_REGION = 'us-east-1'
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
                        // FIX: Using 'bat' command prompt syntax to reliably capture the ECR token without newlines.
                        bat """
                            REM Set environment variables for AWS CLI
                            set AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
                            set AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
                            set AWS_REGION=${AWS_REGION}
                            set AWS_ACCOUNT_ID=${env.AWS_ACCOUNT_ID}

                            echo AWS account: %AWS_ACCOUNT_ID%
                            set ECR_URI=%AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com
                            echo ECR URI: %ECR_URI%

                            echo Attempting docker login using FOR /F workaround...
                            
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
                    
                    # FIX: Use \$env:ECR_REPO directly to form the tag 'repo-name:build-number'
                    \$tag = "\$env:ECR_REPO:\$env:BUILD_NUMBER" 

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
                            set LOCAL_TAG=%LOCAL_REPO_NAME%:%BUILD_NUMBER%
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
                        def ip = powershell(
                            returnStdout: true,
                            script: '''
                                $env:AWS_ACCESS_KEY_ID = "${AWS_ACCESS_KEY_ID}"
                                $env:AWS_SECRET_ACCESS_KEY = "${AWS_SECRET_ACCESS_KEY}"
                                $env:AWS_REGION = "${AWS_REGION}" 

                                aws ec2 describe-instances --region $env:AWS_REGION `
                                    --filters "Name=tag:Name,Values=weather-new" "Name=instance-state-name,Values=running" `
                                    --query "Reservations[0].Instances[0].PublicIpAddress" --output text
                            '''
                        ).trim()
                        
                        // ✅ FINAL FIX: Use Groovy syntax (==) for string comparison
                        if (!ip || ip == 'None') { error "Could not find running EC2 (tag Name=weather-new)" }
                        
                        env.EC2_HOST = ip
                        echo "Resolved EC2 host: ${env.EC2_HOST}"
                    }
                }
            }
        }

        stage('Deploy to EC2') {
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh', keyFileVariable: 'EC2_KEY')]) {
                    powershell """
                        \$keyPath = '${EC2_KEY}'.Replace('\\\\','\\\\\\\\')
                        \$ecr = (Get-Content ecr_info.txt) -replace 'ECR_URI=' ,''
                        
                        Write-Output "Copying deploy.sh to ubuntu@\${env.EC2_HOST}"
                        
                        scp -o StrictHostKeyChecking=no -i \"\$keyPath\" .\\\\deploy.sh ubuntu@\${env.EC2_HOST}:/home/ubuntu/deploy.sh

                        Write-Output "Running deploy on \${env.EC2_HOST}"
                        
                        ssh -o StrictHostKeyChecking=no -i \"\$keyPath\" ubuntu@\${env.EC2_HOST} "bash /home/ubuntu/deploy.sh \$ecr \${env.AWS_REGION}"
                    """
                }
            }
        }
    }
}