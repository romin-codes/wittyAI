import express from "express";
import "dotenv/config";
import cors from "cors";
import mongoose from "mongoose";
import chatRoutes from "./routes/chat.js"

const app = express();
const PORT = process.env.PORT || 8080;

app.use(express.json());
app.use(cors());

app.use("/api",chatRoutes)


app.get("/", (req, res) => {
  res.send("Backend is running 🚀");
});
const connectDB = async () => {
  try {
    await mongoose.connect(process.env.MONGODB_URI);
    console.log("Connected With DB!");
  } catch (err) {
    console.log("Failed to connect with DB", err);
  }
};
app.listen(PORT, () => {
  console.log(`Server is running on PORT:${PORT}`);
  
});
connectDB();

// app.post("/test", async (req, res) => {
//   if (!req.body?.message) {
//     return res.status(400).json({ error: "message is required" });
//   }

//   const options = {
//     method: "POST",
//     headers: {
//       "Content-Type": "application/json",
//       Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
//     },
//     body: JSON.stringify({
//       model: "gpt-4o-mini",
//       messages: [
//         {
//           role: "user",
//           content: req.body.message,
//         },
//       ],
//     }),
//   };

//   try {
//     const response = await fetch(
//       "https://api.openai.com/v1/chat/completions",
//       options,
//     );

//     if (!response.ok) {
//       const error = await response.json();
//       return res.status(response.status).json({ error: error.message });
//     }

//     const data = await response.json();
//     console.log(data.choices[0].message);
//     res.send(data.choices[0].message);
//   } catch (err) {
//     console.error(err);
//     res.status(500).json({ error: err.message });
//   }
// });
