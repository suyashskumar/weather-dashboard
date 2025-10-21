pipeline {
  agent any

  environment {
    AWS_REGION = 'us-east-1'
    ECR_REPO   = 'weather-dashboard'
    // AWS_ACCOUNT_ID and EC2_HOST will be set at runtime via script blocks
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Get AWS Account') {
  steps {
    script {
      // withCredentials injects AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY into the child process
      withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                        usernameVariable: 'AWS_ACCESS_KEY_ID',
                                        passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
        // Call aws directly; don't try to reassign from Groovy env
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
    withCredentials([usernamePassword(credentialsId: 'aws-creds',
                                      usernameVariable: 'AWS_ACCESS_KEY_ID',
                                      passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
      powershell '''
        # withCredentials set AWS env vars for this process automatically
        aws ecr get-login-password --region %AWS_REGION% | docker login --username AWS --password-stdin ${env:AWS_ACCOUNT_ID}.dkr.ecr.%AWS_REGION%.amazonaws.com
      '''
    }
  }
}

    stage('Build image') {
      steps {
        powershell '''
          docker build -t %ECR_REPO%:%BUILD_NUMBER% -f Dockerfile .
        '''
      }
    }

    stage('Tag & Push to ECR') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-creds', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          powershell '''
            $env:AWS_ACCESS_KEY_ID = "${env.AWS_ACCESS_KEY_ID}"
            $env:AWS_SECRET_ACCESS_KEY = "${env.AWS_SECRET_ACCESS_KEY}"
            $ECR_URI = "${env:AWS_ACCOUNT_ID}.dkr.ecr.${env:AWS_REGION}.amazonaws.com/%ECR_REPO%"
            docker tag %ECR_REPO%:%BUILD_NUMBER% $ECR_URI:%BUILD_NUMBER%
            docker push $ECR_URI:%BUILD_NUMBER%
            "ECR_URI=$ECR_URI:$BUILD_NUMBER" | Out-File -Encoding ascii ecr_info.txt
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
          // Use aws-creds to run describe-instances and store EC2 host in env.EC2_HOST
          withCredentials([usernamePassword(credentialsId: 'aws-creds', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
            def ip = powershell(returnStdout: true, script: '''
              $env:AWS_ACCESS_KEY_ID = "${env.AWS_ACCESS_KEY_ID}"
              $env:AWS_SECRET_ACCESS_KEY = "${env.AWS_SECRET_ACCESS_KEY}"
              # Query EC2 by tag name 'weather-new' and get public IP
              aws ec2 describe-instances --region ${env:AWS_REGION} --filters "Name=tag:Name,Values=weather-new" "Name=instance-state-name,Values=running" --query "Reservations[0].Instances[0].PublicIpAddress" --output text
            ''').trim()
            if (!ip || ip == "None") { error "Could not find running EC2 instance with tag Name=weather-new" }
            env.EC2_HOST = ip
            echo "Resolved EC2 host: ${env.EC2_HOST}"
          }
        }
      }
    }

    stage('Deploy to EC2') {
      steps {
        // 'ec2-ssh' should be an SSH private key credential saved in Jenkins (username=ubuntu), we use keyFileVariable
        withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh', keyFileVariable: 'EC2_KEY')]) {
          powershell """
            $EC2_KEY = '${EC2_KEY.replaceAll('\\\\','\\\\\\\\')}'   # Jenkins created temporary path for key
            $ecr = (Get-Content ecr_info.txt) -replace 'ECR_URI=',''
            scp -o StrictHostKeyChecking=no -i $EC2_KEY .\\deploy.sh ubuntu@${env.EC2_HOST}:/home/ubuntu/deploy.sh
            ssh -o StrictHostKeyChecking=no -i $EC2_KEY ubuntu@${env.EC2_HOST} "bash /home/ubuntu/deploy.sh $ecr ${env:AWS_REGION}"
          """
        }
      }
    }
  } // stages
} // pipeline
