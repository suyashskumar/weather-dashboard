pipeline {
  agent any
  environment {
    AWS_REGION = 'us-east-1'           // change if needed
    ECR_REPO = 'weather-dashboard'    // your repo name
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
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
            export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
            export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
            AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
            ECR_URI=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}
            aws ecr create-repository --repository-name ${ECR_REPO} --region ${AWS_REGION} || true
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
        withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh', keyFileVariable: 'EC2_KEY')]) {
          sh '''
            export EC2_HOST=$(aws ec2 describe-instances \
              --region ${AWS_REGION} \
              --filters "Name=tag:Name,Values=weather-new" "Name=instance-state-name,Values=running" \
              --query "Reservations[0].Instances[0].PublicIpAddress" --output text)

            echo "Deploying to $EC2_HOST ..."

            ECR_URI=$(cat ecr_info.txt | cut -d'=' -f2)
            scp -i $EC2_KEY -o StrictHostKeyChecking=no deploy.sh ubuntu@$EC2_HOST:/home/ubuntu/
            ssh -i $EC2_KEY -o StrictHostKeyChecking=no ubuntu@$EC2_HOST "bash /home/ubuntu/deploy.sh ${ECR_URI} ${AWS_REGION}"
          '''
        }
      }
    }
  }
}
