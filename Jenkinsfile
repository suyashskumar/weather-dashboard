pipeline {
  agent any
  environment {
    AWS_REGION = 'us-east-1'
    ECR_REPO   = 'weather-dashboard'
    AWS_ACCOUNT_ID = ''   // will be set in script
    EC2_HOST = ''         // will be set in script
  }
  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Set vars') {
      steps {
        bat """
          for /f "usebackq tokens=*" %%A in ('aws sts get-caller-identity --query Account --output text') do set AWS_ACCOUNT_ID=%%A
          echo AWS_ACCOUNT_ID=%AWS_ACCOUNT_ID%

          for /f "usebackq tokens=*" %%B in ('aws ec2 describe-instances --region %AWS_REGION% --filters "Name=tag:Name,Values=weather-new" "Name=instance-state-name,Values=running" --query "Reservations[0].Instances[0].PublicIpAddress" --output text') do set EC2_HOST=%%B
          echo EC2_HOST=%EC2_HOST%
        """
      }
    }

    stage('Login to ECR') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-creds', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          bat """
            set AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%
            set AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%
            aws ecr get-login-password --region %AWS_REGION% | docker login --username AWS --password-stdin %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com
          """
        }
      }
    }

    stage('Build image') {
      steps {
        bat """
          docker build -t %ECR_REPO%:%BUILD_NUMBER% -f Dockerfile .
        """
      }
    }

    stage('Tag & Push to ECR') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-creds', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          bat """
            set AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%
            set AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%
            set ECR_URI=%AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/%ECR_REPO%
            docker tag %ECR_REPO%:%BUILD_NUMBER% %ECR_URI%:%BUILD_NUMBER%
            docker push %ECR_URI%:%BUILD_NUMBER%
            echo ECR_URI=%ECR_URI%:%BUILD_NUMBER% > ecr_info.txt
          """
        }
      }
      post {
        success { archiveArtifacts artifacts: 'ecr_info.txt' }
      }
    }

    stage('Deploy to EC2') {
      steps {
        withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh', keyFileVariable: 'EC2_KEY')]) {
          bat """
            for /f "usebackq tokens=*" %%A in ('type ecr_info.txt ^| cut -d"=" -f2') do set MY_ECR=%%A
            echo ECR URI is %MY_ECR%
            
            REM Use the dynamically resolved EC2_HOST
            scp -i "%EC2_KEY%" -o StrictHostKeyChecking=no deploy.sh ubuntu@%EC2_HOST%:/home/ubuntu/deploy.sh
            ssh -i "%EC2_KEY%" -o StrictHostKeyChecking=no ubuntu@%EC2_HOST% "bash /home/ubuntu/deploy.sh %MY_ECR% %AWS_REGION%"
          """
        }
      }
    }
  }
}
