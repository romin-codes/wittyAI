import mongoose from "mongoose";

const SourceSchema = new mongoose.Schema(
  {
    source: { type: String, required: true },
    page: { type: Number, default: null },
    score: { type: Number, default: null },
    snippet: { type: String, required: true },
  },
  { _id: false },
);

const MessageSchema = new mongoose.Schema({
  role: {
    type: String,
    enum: ["user", "assistant"],
    required: true,
  },
  content: {
    type: String,
    required: true,
  },
  sources: {
    type: [SourceSchema],
    default: [],
  },
  timestamp: {
    type: Date,
    default: Date.now(),
  },
});

const ThreadSchema = new mongoose.Schema({
  threadId: {
    type: String,
    required: true,
    unique: true,
  },
  title: {
    type: String,
    default: "New Chat",
  },

  messages: [MessageSchema],
  createdAt: {
    type: Date,
    default: Date.now(),
  },
  updatedAt: {
    type: Date,
    default: Date.now(),
  },
});

export default mongoose.model("Thread", ThreadSchema);
