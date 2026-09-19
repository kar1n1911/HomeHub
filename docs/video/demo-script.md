# HomeHub demonstration plan (5-10 minutes)

1. Introduce HomeHub and the user problem.
2. Show the repository boundaries and architecture diagram.
3. Explain each REST service and its owned data.
4. Show the four Docker Hub images.
5. Deploy with `kubectl apply -k kubernetes/`.
6. Show pods, Services, HPA resources, and the database PVC.
7. Open HomeHub from outside Kubernetes and exercise each feature.
8. Scale one API independently and show the additional pods.
9. Delete an API pod and show Kubernetes restoring it.
10. Restart PostgreSQL and show that the data remains.
11. Close with benefits, challenges, and security improvements.

