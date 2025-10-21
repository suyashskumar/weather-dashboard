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
                    powershell """
                        # Assigning Jenkins global variables to the PowerShell environment
                        $env:AWS_ACCESS_KEY_ID = "${AWS_ACCESS_KEY_ID}"
                        $env:AWS_SECRET_ACCESS_KEY = "${AWS_SECRET_ACCESS_KEY}"
                        $env:AWS_REGION = "${AWS_REGION}"
                        $env:AWS_ACCOUNT_ID = "${env.AWS_ACCOUNT_ID}" 

                        Write-Output "aws --version:"
                        aws --version

                        Write-Output "docker --version:"
                        docker --version

                        Write-Output "AWS account: $env:AWS_ACCOUNT_ID"

                        $ecrUri = "$env:AWS_ACCOUNT_ID.dkr.ecr.$env:AWS_REGION.amazonaws.com"
                        Write-Output "ECR URI: $ecrUri"

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
                    if (-not $env:ECR_REPO) { Write-Error "ECR_REPO not set"; exit 1 }
                    # BUILD_NUMBER is a Jenkins variable, so use ${BUILD_NUMBER}
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
                        $env:AWS_ACCOUNT_ID = "${env.AWS_ACCOUNT_ID}"

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
                        # $keyPath is a local PowerShell variable, but it's defined using a Groovy variable (${EC2_KEY})
                        $keyPath = '${EC2_KEY}'.Replace('\\\\','\\\\\\\\')
                        
                        # $ecr is a local PowerShell variable. Groovy needs to ignore the $ sign.
                        $ecr = (Get-Content ecr_info.txt) -replace 'ECR_URI=' ,''
                        
                        # env.EC2_HOST is a Groovy variable and needs interpolation
                        Write-Output "Copying deploy.sh to ubuntu@${env.EC2_HOST}"
                        
                        # $keyPath is a local PowerShell variable. Groovy needs to ignore the $ sign.
                        scp -o StrictHostKeyChecking=no -i \"$keyPath\" .\\\\deploy.sh ubuntu@${env.EC2_HOST}:/home/ubuntu/deploy.sh

                        # Groovy interpolation for EC2_HOST
                        Write-Output "Running deploy on ${env.EC2_HOST}"
                        
                        # $keyPath is a local PowerShell variable. $ecr is a local PowerShell variable.
                        # $env:AWS_REGION is a PowerShell environment variable set from a Groovy variable.
                        # We must escape $ecr to prevent Groovy from trying to interpolate it.
                        ssh -o StrictHostKeyChecking=no -i \"$keyPath\" ubuntu@${env.EC2_HOST} \"bash /home/ubuntu/deploy.sh \$ecr ${env.AWS_REGION}\"
                    """
                }
            }
        }
    }
}