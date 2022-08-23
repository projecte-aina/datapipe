VERSION ?= 0.7.7
GRPC_SOURCES = ./stt_grpc/stt_service_pb2.py ./stt_grpc/stt_service_pb2_grpc.py

all: $(GRPC_SOURCES)

$(GRPC_SOURCES): ./vosk_stt_grpc/stt_service.proto
	python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ./vosk_stt_grpc/stt_service.proto

clean:
	rm $(GRPC_SOURCES)

build:
	docker build . -t paulandrei/datapipe:${VERSION}

push: build
	docker push paulandrei/datapipe:${VERSION}

deploy:
	kustomize build k8s | kubectl apply -f -

undeploy:
	kustomize build k8s | kubectl delete -f -