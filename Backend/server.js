import express from "express";
import "dotenv/config";
import cors from "cors";
import mongoose from "mongoose";
import chatRoutes from "./routes/chat.js";

const app = express();

app.use(express.json());
app.use(cors());

// Cache the Mongo connection across serverless invocations so we don't
// open a new connection on every request (important on Vercel).
let cached = global._mongoose;
if (!cached) {
  cached = global._mongoose = { conn: null, promise: null };
}

const connectDB = async () => {
  if (cached.conn) return cached.conn;
  if (!cached.promise) {
    cached.promise = mongoose
      .connect(process.env.MONGODB_URI, { serverSelectionTimeoutMS: 8000 })
      .then((m) => {
        console.log("Connected With DB!");
        return m;
      });
  }
  try {
    cached.conn = await cached.promise;
  } catch (err) {
    // Reset the cached promise so the next request can retry instead of
    // reusing a permanently-rejected promise.
    cached.promise = null;
    throw err;
  }
  return cached.conn;
};

// Ensure the DB is connected before handling any request.
app.use(async (req, res, next) => {
  try {
    await connectDB();
    next();
  } catch (err) {
    console.log("Failed to connect with DB", err);
    res.status(500).json({
      error: "Database connection failed",
      // TEMPORARY: expose the real reason for debugging the deployment.
      detail: err?.message,
    });
  }
});

app.get("/", (req, res) => {
  res.send("WittyAI backend is running");
});

app.use("/api", chatRoutes);

// Only start a persistent server when running locally. On Vercel the app is
// used as a serverless handler (Vercel sets process.env.VERCEL).
if (!process.env.VERCEL) {
  const PORT = process.env.PORT || 8080;
  app.listen(PORT, () => {
    console.log(`Server is running on PORT:${PORT}`);
  });
}

export default app;
