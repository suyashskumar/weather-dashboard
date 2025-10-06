pipeline {
  agent any
  environment {
    IMAGE = "yourdockerhubusername/weather-dashboard" // change or leave
    CONTAINER = "weather_app"
  }
  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }
    stage('Prepare env') {
      steps {
        // pulls OPENWEATHER_API_KEY from Jenkins credentials (create secret text with id openweather-key)
        withCredentials([string(credentialsId: 'openweather-key', variable: 'OPENWEATHER_API_KEY')]) {
          sh 'echo "OPENWEATHER_API_KEY=${OPENWEATHER_API_KEY}" > .env'
        }
      }
    }
    stage('Build image') {
      steps {
        sh 'docker build -t $IMAGE:$BUILD_NUMBER .'
      }
    }
    stage('Deploy') {
      steps {
        sh '''
          docker stop $CONTAINER || true
          docker rm $CONTAINER || true
          docker run -d --name $CONTAINER -p 80:5000 --env-file .env $IMAGE:$BUILD_NUMBER
        '''
      }
    }
  }
  post {
    always {
      sh 'docker ps -a || true'
    }
  }
}
