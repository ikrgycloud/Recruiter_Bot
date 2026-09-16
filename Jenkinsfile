pipeline {

    agent any

    environment {

        AWS_REGION = "eu-north-1"

        ACCOUNT_ID = "032844082845"

        BACKEND_REPO =
            "032844082845.dkr.ecr.eu-north-1.amazonaws.com/recruiter-backend"

        FRONTEND_REPO =
            "032844082845.dkr.ecr.eu-north-1.amazonaws.com/recruiter-frontend"

        IMAGE_TAG = "${BUILD_NUMBER}"

        APP_SERVER = "ubuntu@16.16.216.155"

        APP_DIR = "/opt/recruiter"
    }

    stages {

        stage('Checkout') {
            steps {
                git branch: 'main',
                    url: 'https://github.com/ikrgycloud/Recruiter_Bot.git'
            }
        }

        stage('Docker Login') {
            steps {

                sh '''
                    aws ecr get-login-password \
                    --region ${AWS_REGION} \
                    | docker login \
                    --username AWS \
                    --password-stdin \
                    ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
                '''
            }
        }

        stage('Build Backend') {
            steps {

                sh '''
                    docker build \
                    -t ${BACKEND_REPO}:${IMAGE_TAG} \
                    ./backend
                '''
            }
        }

        stage('Build Frontend') {
            steps {

                sh '''
                    docker build \
                    -t ${FRONTEND_REPO}:${IMAGE_TAG} \
                    ./frontend
                '''
            }
        }

        stage('Push Backend') {
            steps {

                sh '''
                    docker push ${BACKEND_REPO}:${IMAGE_TAG}
                '''
            }
        }

        stage('Push Frontend') {
            steps {

                sh '''
                    docker push ${FRONTEND_REPO}:${IMAGE_TAG}
                '''
            }
        }

        stage('Deploy') {
            steps {

                sh '''
                    ssh -o StrictHostKeyChecking=no ${APP_SERVER} "
                        cd ${APP_DIR} &&
                        export IMAGE_TAG=${IMAGE_TAG} &&
                        docker compose -f docker-compose.prod.yml pull &&
                        docker compose -f docker-compose.prod.yml up -d
                    "
                '''
            }
        }

        stage('Health Check') {
            steps {

                sh '''
                    sleep 15

                    ssh -o StrictHostKeyChecking=no ${APP_SERVER} "
                        docker ps --format 'table {{.Names}}\\t{{.Status}}'
                    "
                '''
            }
        }
    }

    post {

        success {
            echo "Recruiter Bot deployment successful."
        }

        failure {
            echo "Recruiter Bot deployment failed."
        }
    }
}
