# DATA-PROJECT-2-EDEM

BASH
docker run --rm -it -p 8085:8085 --name pubsub-emulator gcr.io/google.com/cloudsdktool/cloud-sdk:emulators gcloud beta emulators pubsub start --host-port=0.0.0.0:8085 --project=local-project

NO cierres la terminal del emulador mientras se prubea -- los topics viven en memoria -- , si se muere se pierde todo. Hay que dejarlo corriendo en una pestaña aparte.

