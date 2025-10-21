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
                    # BUILD_NUMBER is a Jenkins environment variable, so we must use brackets for interpolation
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
                        # The variable $keyPath is created within the script using a Groovy variable (${EC2_KEY})
                        $keyPath = '${EC2_KEY}'.Replace('\\\\','\\\\\\\\')
                        
                        # The variable $ecr is created within the script, Groovy must not interpolate it.
                        $ecr = (Get-Content ecr_info.txt) -replace 'ECR_URI=' ,''
                        
                        # Use Jenkins variable interpolation for the hostname
                        Write-Output "Copying deploy.sh to ubuntu@${env.EC2_HOST}"
                        
                        # $keyPath is a local variable, $env.EC2_HOST is Groovy interpolated
                        scp -o StrictHostKeyChecking=no -i \"$keyPath\" .\\\\deploy.sh ubuntu@${env.EC2_HOST}:/home/ubuntu/deploy.sh

                        # Use Jenkins variable interpolation for the hostname
                        Write-Output "Running deploy on ${env.EC2_HOST}"
                        
                        # ESCAPE \$ecr: This variable is defined INSIDE the PowerShell script, so Groovy must treat it as a literal.
                        # $env.AWS_REGION is a Jenkins variable, so it's safely interpolated using ${env.AWS_REGION}
                        ssh -o StrictHostKeyChecking=no -i \"$keyPath\" ubuntu@${env.EC2_HOST} \"bash /home/ubuntu/deploy.sh \$ecr ${env.AWS_REGION}\"
                    """
                }
            }
        }
    }
}