pipeline {
  agent any

  environment {
    AWS_REGION = 'us-east-1'          // Change if needed
    ECR_REPO   = 'weather-dashboard'  // Your ECR repo name
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Build image') {
      steps {
        sh 'docker build -t ${ECR_REPO}:${BUILD_NUMBER} .'
      }
    }

    stage('Push to ECR') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-creds', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh '''
            set -e
            export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
            export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}

            AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
            ECR_URI=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}

            # Ensure repo exists
            aws ecr describe-repositories --repository-names ${ECR_REPO} --region ${AWS_REGION} >/dev/null 2>&1 || \
              aws ecr create-repository --repository-name ${ECR_REPO} --region ${AWS_REGION}

            # Login & push
            aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URI}
            docker tag ${ECR_REPO}:${BUILD_NUMBER} ${ECR_URI}:${BUILD_NUMBER}
            docker push ${ECR_URI}:${BUILD_NUMBER}

            echo "ECR_URI=${ECR_URI}:${BUILD_NUMBER}" > ecr_info.txt
          '''
        }
      }
      post {
        success {
          archiveArtifacts artifacts: 'ecr_info.txt', fingerprint: true
        }
      }
    }

    stage('Deploy to EC2') {
      steps {
        withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh', keyFileVariable: 'EC2_KEY'),
                         usernamePassword(credentialsId: 'aws-creds', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh '''
            set -e
            export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
            export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}

            # Dynamically fetch EC2's current public IP by instance name tag
            EC2_HOST=$(aws ec2 describe-instances \
              --region ${AWS_REGION} \
              --filters "Name=tag:Name,Values=weather-new" "Name=instance-state-name,Values=running" \
              --query "Reservations[0].Instances[0].PublicIpAddress" --output text)

            echo "Deploying to EC2 instance at: $EC2_HOST"

            ECR_URI=$(cut -d'=' -f2 < ecr_info.txt)

            scp -i $EC2_KEY -o StrictHostKeyChecking=no deploy.sh ubuntu@$EC2_HOST:/home/ubuntu/
            ssh -i $EC2_KEY -o StrictHostKeyChecking=no ubuntu@$EC2_HOST "bash /home/ubuntu/deploy.sh ${ECR_URI} ${AWS_REGION}"
          '''
        }
      }
    }
  }
}
