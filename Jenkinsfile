pipeline {
    agent any

    environment {
        AWS_REGION = 'us-east-1'
        ECR_REPO   = 'weather-dashboard'
        // AWS_ACCOUNT_ID and EC2_HOST will be set at runtime
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
                        // This stage is safe with single quotes because no global env vars are interpolated here
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
                withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                                 usernameVariable: 'AWS_ACCESS_KEY_ID',
                                                 passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                    // Triple double-quotes are used, and backslashes are removed
                    powershell """
                        # Use # for PowerShell comments
                        $env:AWS_ACCESS_KEY_ID = "${AWS_ACCESS_KEY_ID}"
                        $env:AWS_SECRET_ACCESS_KEY = "${AWS_SECRET_ACCESS_KEY}"
                        $env:AWS_REGION = "${AWS_REGION}"
                        # Use the globally set AWS Account ID from the previous stage
                        $env:AWS_ACCOUNT_ID = "${env.AWS_ACCOUNT_ID}" 

                        Write-Output "aws --version:"
                        aws --version

                        Write-Output "docker --version:"
                        docker --version

                        Write-Output "AWS account: $env:AWS_ACCOUNT_ID"

                        $ecrUri = "$env:AWS_ACCOUNT_ID.dkr.ecr.$env:AWS_REGION.amazonaws.com"
                        Write-Output "ECR URI: $ecrUri"

                        # This command now works because $env:AWS_REGION is correctly set
                        $password = aws ecr get-login-password --region $env:AWS_REGION
                        if (-not $password) { Write-Error "Failed to get ECR password"; exit 3 }

                        Write-Output "Attempting docker login..."
                        $password | docker login --username AWS --password-stdin $ecrUri
                        if ($LASTEXITCODE -ne 0) { Write-Error "Docker login failed"; exit 5 }

                        Write-Output "Docker login succeeded."
                    """
                }
            }
        }

        stage('Build image') {
            steps {
                powershell """
                    # Changed comment to #
                    if (-not $env:ECR_REPO) { Write-Error "ECR_REPO not set"; exit 1 }
                    # Interpolate BUILD_NUMBER from Jenkins env
                    $tag = "\${ECR_REPO}:\${BUILD_NUMBER}" 
                    Write-Output "Building Docker image $tag"
                    docker build -t $tag -f Dockerfile .
                    if ($LASTEXITCODE -ne 0) { Write-Error "Docker build failed"; exit 1 }
                """
            }
        }

        stage('Tag & Push to ECR') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                                 usernameVariable: 'AWS_ACCESS_KEY_ID',
                                                 passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                    powershell """
                        $env:AWS_ACCESS_KEY_ID = "${AWS_ACCESS_KEY_ID}"
                        $env:AWS_SECRET_ACCESS_KEY = "${AWS_SECRET_ACCESS_KEY}"
                        $env:AWS_REGION = "${AWS_REGION}"
                        $env:AWS_ACCOUNT_ID = "${env.AWS_ACCOUNT_ID}" # Ensure Account ID is available

                        $ecrUri = "$env:AWS_ACCOUNT_ID.dkr.ecr.$env:AWS_REGION.amazonaws.com/$env:ECR_REPO"
                        $localTag = "$env:ECR_REPO:$env:BUILD_NUMBER"
                        $remoteTag = "$ecrUri:$env:BUILD_NUMBER"

                        Write-Output "Tagging $localTag -> $remoteTag"
                        docker tag $localTag $remoteTag
                        if ($LASTEXITCODE -ne 0) { Write-Error "Docker tag failed"; exit 1 }

                        Write-Output "Pushing $remoteTag"
                        docker push $remoteTag
                        if ($LASTEXITCODE -ne 0) { Write-Error "Docker push failed"; exit 1 }

                        "ECR_URI=$remoteTag" | Out-File -Encoding ascii ecr_info.txt
                    """
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
                        # Backslashes removed from PowerShell $ variables
                        $keyPath = '${EC2_KEY}'.Replace('\\\\','\\\\\\\\')
                        $ecr = (Get-Content ecr_info.txt) -replace 'ECR_URI=' ,''
                        Write-Output "Copying deploy.sh to ubuntu@${env.EC2_HOST}"
                        scp -o StrictHostKeyChecking=no -i \"$keyPath\" .\\\\deploy.sh ubuntu@${env.EC2_HOST}:/home/ubuntu/deploy.sh

                        Write-Output "Running deploy on ${env.EC2_HOST}"
                        ssh -o StrictHostKeyChecking=no -i \"$keyPath\" ubuntu@${env.EC2_HOST} \"bash /home/ubuntu/deploy.sh $ecr ${env.AWS_REGION}\"
                    """
                }
            }
        }
    }
}