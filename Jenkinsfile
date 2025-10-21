pipeline {
  agent any

  environment {
    AWS_REGION = 'us-east-1'
    ECR_REPO   = 'weather-dashboard'
    // AWS_ACCOUNT_ID and EC2_HOST will be set at runtime
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Get AWS Account') {
      steps {
        script {
          // Use Jenkins credential (username=ACCESS_KEY, password=SECRET)
          withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                            usernameVariable: 'AWS_ACCESS_KEY_ID',
                                            passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
            // Call aws directly -- the child process will see the injected env vars
            def acct = powershell(returnStdout: true, script: 'aws sts get-caller-identity --query Account --output text').trim()
            if (!acct) { error "Failed to get AWS account ID" }
            env.AWS_ACCOUNT_ID = acct
            echo "AWS account: ${env.AWS_ACCOUNT_ID}"
          }
        }
      }
    }

    stage('Login to ECR') {
      steps {
        // Keep credentials in scope so aws CLI inside powershell can use them
        withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                          usernameVariable: 'AWS_ACCESS_KEY_ID',
                                          passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          // Use triple single quotes to prevent Groovy interpolation; use PowerShell $env:... inside.
          powershell '''
            # Construct ECR URI from process env vars
            if (-not $env:AWS_ACCOUNT_ID) { Write-Error "AWS_ACCOUNT_ID is not set"; exit 1 }
            $ecrUri = "$env:AWS_ACCOUNT_ID.dkr.ecr.$env:AWS_REGION.amazonaws.com"
            Write-Output "Logging in to ECR: $ecrUri"
            aws ecr get-login-password --region $env:AWS_REGION | docker login --username AWS --password-stdin $ecrUri
          '''
        }
      }
    }

    stage('Build image') {
      steps {
        powershell '''
          if (-not $env:ECR_REPO) { Write-Error "ECR_REPO not set"; exit 1 }
          $tag = "$env:ECR_REPO:$env:BUILD_NUMBER"
          Write-Output "Building Docker image $tag"
          docker build -t $tag -f Dockerfile .
        '''
      }
    }

    stage('Tag & Push to ECR') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                          usernameVariable: 'AWS_ACCESS_KEY_ID',
                                          passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          powershell '''
            $ecrUri = "$env:AWS_ACCOUNT_ID.dkr.ecr.$env:AWS_REGION.amazonaws.com/$env:ECR_REPO"
            $localTag = "$env:ECR_REPO:$env:BUILD_NUMBER"
            $remoteTag = "$ecrUri:$env:BUILD_NUMBER"
            Write-Output "Tagging $localTag -> $remoteTag"
            docker tag $localTag $remoteTag
            Write-Output "Pushing $remoteTag"
            docker push $remoteTag
            "ECR_URI=$remoteTag" | Out-File -Encoding ascii ecr_info.txt
          '''
        }
      }
      post {
        success { archiveArtifacts artifacts: 'ecr_info.txt' }
      }
    }

    stage('Resolve EC2 IP (by tag)') {
      steps {
        script {
          withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                            usernameVariable: 'AWS_ACCESS_KEY_ID',
                                            passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
            def ip = powershell(returnStdout: true, script: '''
              aws ec2 describe-instances --region $env:AWS_REGION `
                --filters "Name=tag:Name,Values=weather-new" "Name=instance-state-name,Values=running" `
                --query "Reservations[0].Instances[0].PublicIpAddress" --output text
            ''').trim()
            if (!ip || ip == 'None') { error "Could not find running EC2 (tag Name=weather-new)" }
            env.EC2_HOST = ip
            echo "Resolved EC2 host: ${env.EC2_HOST}"
          }
        }
      }
    }

    stage('Deploy to EC2') {
      steps {
        // ec2-ssh is of kind SSH username private key (username=ubuntu)
        withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh', keyFileVariable: 'EC2_KEY')]) {
          powershell """
            $keyPath = '${EC2_KEY}'.Replace('\\','\\\\')
            $ecr = (Get-Content ecr_info.txt) -replace 'ECR_URI=',''
            Write-Output \"Copying deploy.sh to ubuntu@${env:EC2_HOST}\"
            scp -o StrictHostKeyChecking=no -i \"$keyPath\" .\\deploy.sh ubuntu@${env:EC2_HOST}:/home/ubuntu/deploy.sh
            Write-Output \"Running deploy on ${env:EC2_HOST}\"
            ssh -o StrictHostKeyChecking=no -i \"$keyPath\" ubuntu@${env:EC2_HOST} \"bash /home/ubuntu/deploy.sh $ecr $env:AWS_REGION\"
          """
        }
      }
    }
  } // stages
} // pipeline
