pipeline {
  agent any

  environment {
    AWS_REGION = 'us-east-1'
    ECR_REPO   = 'weather-dashboard'
    // AWS_ACCOUNT_ID and EC2_HOST will be set dynamically
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Get AWS Account') {
      steps {
        script {
          withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                            usernameVariable: 'AWS_ACCESS_KEY_ID',
                                            passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
            // Export env vars for PowerShell
            powershell """
              \$env:AWS_ACCESS_KEY_ID='${AWS_ACCESS_KEY_ID}'
              \$env:AWS_SECRET_ACCESS_KEY='${AWS_SECRET_ACCESS_KEY}'
              \$env:AWS_REGION='${AWS_REGION}'
              \$env:AWS_ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text).Trim()
              if (-not \$env:AWS_ACCOUNT_ID) { Write-Error 'Failed to get AWS account ID'; exit 1 }
              Write-Output "AWS account: \$env:AWS_ACCOUNT_ID"
            """
          }
        }
      }
    }

    stage('Login to ECR') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                          usernameVariable: 'AWS_ACCESS_KEY_ID',
                                          passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          powershell """
            \$env:AWS_ACCESS_KEY_ID='${AWS_ACCESS_KEY_ID}'
            \$env:AWS_SECRET_ACCESS_KEY='${AWS_SECRET_ACCESS_KEY}'
            \$env:AWS_REGION='${AWS_REGION}'
            \$ecrUri = "\$env:AWS_ACCOUNT_ID.dkr.ecr.\$env:AWS_REGION.amazonaws.com"
            \$password = aws ecr get-login-password --region \$env:AWS_REGION
            if (-not \$password) { Write-Error 'Failed to get ECR password'; exit 1 }
            docker login --username AWS --password \$password \$ecrUri
            if (\$LASTEXITCODE -ne 0) { Write-Error 'Docker login failed'; exit 1 }
          """
        }
      }
    }

    stage('Build image') {
      steps {
        powershell """
          \$tag = "\$env:ECR_REPO:\$env:BUILD_NUMBER"
          Write-Output "Building Docker image \$tag"
          docker build -t \$tag -f Dockerfile .
          if (\$LASTEXITCODE -ne 0) { Write-Error 'Docker build failed'; exit 1 }
        """
      }
    }

    stage('Tag & Push to ECR') {
      steps {
        powershell """
          \$ecrUri = "\$env:AWS_ACCOUNT_ID.dkr.ecr.\$env:AWS_REGION.amazonaws.com/\$env:ECR_REPO"
          \$localTag = "\$env:ECR_REPO:\$env:BUILD_NUMBER"
          \$remoteTag = "\$ecrUri:\$env:BUILD_NUMBER"
          Write-Output "Tagging \$localTag -> \$remoteTag"
          docker tag \$localTag \$remoteTag
          Write-Output "Pushing \$remoteTag"
          docker push \$remoteTag
          if (\$LASTEXITCODE -ne 0) { Write-Error 'Docker push failed'; exit 1 }
          "ECR_URI=\$remoteTag" | Out-File -Encoding ascii ecr_info.txt
        """
      }
      post { success { archiveArtifacts artifacts: 'ecr_info.txt' } }
    }

    stage('Resolve EC2 IP (by tag)') {
      steps {
        script {
          withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                            usernameVariable: 'AWS_ACCESS_KEY_ID',
                                            passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
            def ip = powershell(returnStdout: true, script: """
              \$env:AWS_ACCESS_KEY_ID='${AWS_ACCESS_KEY_ID}'
              \$env:AWS_SECRET_ACCESS_KEY='${AWS_SECRET_ACCESS_KEY}'
              \$env:AWS_REGION='${AWS_REGION}'
              aws ec2 describe-instances --region \$env:AWS_REGION `
                --filters "Name=tag:Name,Values=weather-new" "Name=instance-state-name,Values=running" `
                --query "Reservations[0].Instances[0].PublicIpAddress" --output text
            """).trim()
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
            \$ecr = (Get-Content ecr_info.txt) -replace 'ECR_URI=',''
            Write-Output "Copying deploy.sh to ubuntu@\$env:EC2_HOST"
            scp -o StrictHostKeyChecking=no -i "\$keyPath" .\\deploy.sh ubuntu@\$env:EC2_HOST:/home/ubuntu/deploy.sh
            Write-Output "Running deploy on \$env:EC2_HOST"
            ssh -o StrictHostKeyChecking=no -i "\$keyPath" ubuntu@\$env:EC2_HOST "bash /home/ubuntu/deploy.sh \$ecr \$env:AWS_REGION"
          """
        }
      }
    }
  }
}
