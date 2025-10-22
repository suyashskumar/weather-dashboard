pipeline {
    agent any

    environment {
        // 🚨 FIX: Ensure region matches your EC2 and ECR location
        AWS_REGION = 'eu-north-1'
        ECR_REPO   = 'weather-dashboard'
        // Default EC2 IP to allow manual testing/debugging if resolution fails
        EC2_HOST = ''
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
                        // Use powershell to get AWS Account ID
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
                    // Build using the specific ECR URI for base image reference (as Dockerfile is local)
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
                    // 🚨 FIX: Use the standard 'aws-creds' ID and usernamePassword binding
                    withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                                     usernameVariable: 'AWS_ACCESS_KEY_ID',
                                                     passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                        powershell """
                            \$ErrorActionPreference = "Stop" # Exit on error

                            // Setting AWS creds for this powershell block (even though AWS_ACCESS_KEY_ID/SECRET are masked/bound by Jenkins)
                            \$env:AWS_ACCESS_KEY_ID = "${AWS_ACCESS_KEY_ID}"
                            \$env:AWS_SECRET_ACCESS_KEY = "${AWS_SECRET_ACCESS_KEY}"
                            \$AWS_REGION = "\${env.AWS_REGION}"
                            
                            Write-Host "Searching for running EC2 instance in \$AWS_REGION with tag Name=weather-new..."

                            // Use the AWS CLI to query the PublicIpAddress
                            \$EC2_IP = aws ec2 describe-instances `
                                --region \$AWS_REGION `
                                --filters "Name=tag:Name,Values=weather-new" "Name=instance-state-name,Values=running" `
                                --query "Reservations[0].Instances[0].PublicIpAddress" `
                                --output text

                            // Trim any whitespace from the output (PowerShell's .trim() is more reliable than batch)
                            \$EC2_IP = \$EC2_IP.Trim()

                            // Check if the IP was found
                            if (-not \$EC2_IP -or \$EC2_IP -eq "None") {
                                Write-Error "ERROR: Could not find running EC2 (tag Name=weather-new) in \$AWS_REGION. Check instance status."
                                exit 1
                            }

                            Write-Host "Resolved EC2 Host IP: \$EC2_IP"
                            
                            // Write the resolved IP to a temporary file
                            echo "EC2_HOST=\$EC2_IP" | Out-File -FilePath "ec2_host_temp.txt" -Encoding ASCII -Force
                        """
                        // Read the output back into the Jenkins environment
                        def ip = readFile('ec2_host_temp.txt').trim().replace('EC2_HOST=','')
                        env.EC2_HOST = ip.trim()
                        // clean up temp file
                        powershell 'Remove-Item -Path "ec2_host_temp.txt" -Force'
                    }
                }
            }
        }

        stage('Deploy to EC2') {
            steps {
                // EC2_HOST is now guaranteed to be set if the previous stage passed
                withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh', keyFileVariable: 'EC2_KEY')]) {
                    powershell """
                        \$ErrorActionPreference = "Stop"

                        // Get ECR URI from artifact file
                        \$ecr = (Get-Content ecr_info.txt) -replace 'ECR_URI=' ,''

                        // PowerShell requires backslashes in the key path to be escaped for SSH/SCP
                        \$keyPath = '${EC2_KEY}'.Replace('\\\\','\\\\\\\\')
                        
                        Write-Output "Copying deploy.sh to ubuntu@\${env.EC2_HOST}"
                        
                        // Copy deploy.sh
                        scp -o StrictHostKeyChecking=no -i \"\$keyPath\" .\\\\deploy.sh ubuntu@\${env.EC2_HOST}:/home/ubuntu/deploy.sh
                        if (\$LASTEXITCODE -ne 0) { Write-Error "SCP failed"; exit 1 }

                        Write-Output "Running deploy on \${env.EC2_HOST}"
                        
                        // Execute deploy.sh with the ECR URI and AWS_REGION as arguments
                        ssh -o StrictHostKeyChecking=no -i \"\$keyPath\" ubuntu@\${env.EC2_HOST} "bash /home/ubuntu/deploy.sh \$ecr \${env.AWS_REGION}"
                        if (\$LASTEXITCODE -ne 0) { Write-Error "SSH deploy command failed"; exit 1 }

                        Write-Host "Deployment to \${env.EC2_HOST} succeeded."
                    """
                }
            }
        }
    }
}