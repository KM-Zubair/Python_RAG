FROM python:3.9

ENV HUGGINGFACEHUB_API_TOKEN=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
ENV API_KEY=mO26rO9_o2JNdXEQh-IDE1ZLSmf7z6ytc8n_mQ_rU8T4
ENV IBM_CLOUD_URL=https://us-south.ml.cloud.ibm.com
ENV PROJECT_ID=2bccaf1d-1983-4e8b-9837-6b15313ffa7b
ENV URL_D=https://api.au-syd.discovery.watson.cloud.ibm.com/instances/3bf8d48f-bf8a-4290-b61f-9f9a34b72f7b
ENV PROJECT_ID_D=40650b85-ab34-4f2e-81bc-f29b7985674d
ENV COLLECTION_ID_D=4f980946-cbe2-90a3-0000-018ba46d7231
ENV MONGO_DB_URI=mongodb+srv://cooldudeuser2:1HGS1hrKIdKFCqOa@dudecluster.o39qn4s.mongodb.net/?retryWrites=true&w=majority
ENV MONGO_DB_NAME=watsonx-demo
ENV MONGO_COLLECTION_NAME=documents
ENV COS_API_KEY_ID=bI0FwrGNmmumLDaGs6tfy2d51xHarLwQ-sQk5vn9B6W6
ENV COS_INSTANCE_CRN=crn:v1:bluemix:public:cloud-object-storage:global:a/6af6e0b1f2e54fb4956dd8d9334951f1:9fd64a5f-800a-49e6-bbff-7eab204d1c82:bucket:dudebucket
ENV COS_ENDPOINT=https://s3.au-syd.cloud-object-storage.appdomain.cloud
ENV COS_BUCKET_NAME=dudebucket

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD [ "streamlit", "run", "app.py" ]
