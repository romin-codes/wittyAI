import "./ChatWindow.css";
import Chat from "./Chat.jsx";
import { MyContext } from "./MyContext.jsx";
import { useContext, useState, useEffect, useRef } from "react";
import { ScaleLoader } from "react-spinners";
import { API_BASE_URL } from "./config.js";

function ChatWindow() {
  const {
    prompt,
    setPrompt,
    reply,
    setReply,
    currThreadId,
    setPrevChats,
    setNewChat,
  } = useContext(MyContext);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [docs, setDocs] = useState([]);
  const [showUrlBar, setShowUrlBar] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState("");
  const fileInputRef = useRef(null);
  const latestSourcesRef = useRef([]);

  const fetchDocuments = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents`);
      if (!response.ok) return;
      const data = await response.json();
      setDocs(data.documents || []);
    } catch {
      // ignore if ai-service is offline on initial load
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/documents`);
        if (!response.ok || cancelled) return;
        const data = await response.json();
        if (!cancelled) setDocs(data.documents || []);
      } catch {
        // ignore if ai-service is offline on initial load
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const getReply = async () => {
    if (!prompt.trim() || loading) return;
    setLoading(true);
    setNewChat(false);
    console.log("message ", prompt, " thread ", currThreadId);

    const options = {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: prompt,
        threadId: currThreadId,
      }),
    };
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, options);
      const res = await response.json();
      console.log(res);
      latestSourcesRef.current = res.sources || [];
      setReply(res.reply);
    } catch (error) {
      console.log(error);
    }
    setLoading(false);
  };

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setIngesting(true);
    setIngestStatus(`Indexing ${file.name}...`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${API_BASE_URL}/api/documents/file`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        setIngestStatus(`Error: ${data.error || "Upload failed"}`);
      } else {
        setIngestStatus(`Indexed ${data.source} (${data.chunks_added} chunks)`);
        await fetchDocuments();
      }
    } catch (error) {
      setIngestStatus(`Error: ${error.message}`);
    }
    setIngesting(false);
  };

  const handleUrlIngest = async () => {
    const trimmed = urlInput.trim();
    if (!trimmed || ingesting) return;

    setIngesting(true);
    setIngestStatus("Fetching & indexing URL...");
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents/url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: trimmed }),
      });
      const data = await response.json();
      if (!response.ok) {
        setIngestStatus(`Error: ${data.error || "URL ingest failed"}`);
      } else {
        setIngestStatus(`Indexed URL (${data.chunks_added} chunks)`);
        setUrlInput("");
        setShowUrlBar(false);
        await fetchDocuments();
      }
    } catch (error) {
      setIngestStatus(`Error: ${error.message}`);
    }
    setIngesting(false);
  };

  const handleClearDocs = async () => {
    setIngesting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents`, {
        method: "DELETE",
      });
      if (response.ok) {
        setDocs([]);
        setIngestStatus("Cleared all loaded documents.");
      }
    } catch (error) {
      setIngestStatus(`Error: ${error.message}`);
    }
    setIngesting(false);
  };

  // Append new chat to prev chat
  useEffect(() => {
    if (prompt && reply) {
      const sources = latestSourcesRef.current;
      setPrevChats((prevChats) => [
        ...prevChats,
        {
          role: "user",
          content: prompt,
        },
        {
          role: "assistant",
          content: reply,
          sources,
        },
      ]);
    }
    setPrompt("");
  }, [reply]);

  const handleProfileClick = () => {
    setIsOpen(!isOpen);
  };

  return (
    <div className="chatWindow">
      <div className="nav">
        <span>
          WittyAI<i className="fa-solid fa-chevron-down"></i>
        </span>
        <div className="userIconDiv" onClick={handleProfileClick}>
          <span className="userIcon">
            <i className="fa-solid fa-user"></i>
          </span>
        </div>
      </div>
      {isOpen && (
        <div className="dropDown">
          <div className="dropDownItem">
            <i className="fa-solid fa-gear"></i>Settings
          </div>
          <div className="dropDownItem">
            <i className="fa-solid fa-cloud-arrow-up"></i>Upgrade Plan
          </div>
          <div className="dropDownItem">
            <i className="fa-solid fa-right-from-bracket"></i>Log Out
          </div>
        </div>
      )}

      <Chat></Chat>

      <ScaleLoader color="white" loading={loading}></ScaleLoader>

      <div className="chatInput">
        {(docs.length > 0 || ingestStatus) && (
          <div className="docBar">
            <div className="docChips">
              {docs.map((doc) => (
                <span className="docChip" key={doc.source} title={doc.source}>
                  <i className="fa-solid fa-file-lines"></i>
                  <span className="docChipName">{doc.source}</span>
                  <span className="docChipCount">{doc.chunks}</span>
                </span>
              ))}
              {docs.length > 0 && (
                <button
                  type="button"
                  className="docClearBtn"
                  onClick={handleClearDocs}
                  disabled={ingesting}
                  title="Clear all indexed documents"
                >
                  Clear
                </button>
              )}
            </div>
            {ingestStatus && <span className="docStatus">{ingestStatus}</span>}
          </div>
        )}

        {showUrlBar && (
          <div className="urlBar">
            <input
              type="url"
              className="urlInput"
              placeholder="Paste a webpage URL (https://...)"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => (e.key === "Enter" ? handleUrlIngest() : "")}
              disabled={ingesting}
            />
            <button
              type="button"
              className="urlSubmitBtn"
              onClick={handleUrlIngest}
              disabled={ingesting || !urlInput.trim()}
            >
              {ingesting ? "Adding..." : "Add URL"}
            </button>
          </div>
        )}

        <div className="inputBox">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md"
            style={{ display: "none" }}
            onChange={handleFileChange}
          />
          <div className="inputActions">
            <button
              type="button"
              className="iconBtn"
              onClick={() => fileInputRef.current?.click()}
              disabled={ingesting}
              title="Upload PDF, TXT, or MD"
            >
              <i className="fa-solid fa-paperclip"></i>
            </button>
            <button
              type="button"
              className={`iconBtn ${showUrlBar ? "active" : ""}`}
              onClick={() => setShowUrlBar((prev) => !prev)}
              disabled={ingesting}
              title="Index a webpage URL"
            >
              <i className="fa-solid fa-link"></i>
            </button>
          </div>
          <input
            className="promptInput"
            placeholder="Ask Anything (or upload a PDF/URL to chat with docs)"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => (e.key === "Enter" ? getReply() : "")}
          ></input>
          <div id="submit" onClick={getReply}>
            <i className="fa-solid fa-paper-plane"></i>
          </div>
        </div>
        <p className="info">WittyAI can make mistakes. Check important info.</p>
      </div>
    </div>
  );
}

export default ChatWindow;
