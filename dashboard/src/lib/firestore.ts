import { initializeApp, getApps, cert } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";

if (!getApps().length) {
  const projectId = process.env.FIRESTORE_PROJECT_ID;
  const credentialsPath = process.env.GOOGLE_APPLICATION_CREDENTIALS;

  if (!projectId) {
    throw new Error("FIRESTORE_PROJECT_ID environment variable is required");
  }

  if (credentialsPath) {
    initializeApp({
      credential: cert(credentialsPath),
      projectId,
    });
  } else {
    // Use default credentials (e.g., when running on GCP)
    initializeApp({
      projectId,
    });
  }
}

export const db = getFirestore();
