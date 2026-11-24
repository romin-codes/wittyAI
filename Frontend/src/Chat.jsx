import { useContext, useState, useEffect } from "react";
import "./Chat.css";
import { MyContext } from "./MyContext";
import ReactMarkdown from "react-markdown";
import RehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

function SourcesList({ sources }) {
  if (!sources?.length) return null;

  return (
    <details className="sourcesBox">
      <summary className="sourcesSummary">
        <i className="fa-solid fa-book-open"></i> Sources ({sources.length})
      </summary>
      <div className="sourcesList">
        {sources.map((item, idx) => {
          const isUrl = /^https?:\/\//i.test(item.source);
          return (
            <div className="sourceItem" key={`${item.source}-${idx}`}>
              <div className="sourceHeader">
                <span className="sourceBadge">[{idx + 1}]</span>
                {isUrl ? (
                  <a
                    className="sourceName"
                    href={item.source}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {item.source}
                  </a>
                ) : (
                  <span className="sourceName">{item.source}</span>
                )}
                {item.page != null && (
                  <span className="sourceMeta">p.{item.page}</span>
                )}
                {item.score != null && (
                  <span className="sourceMeta">
                    {Math.round(item.score * 100)}% match
                  </span>
                )}
              </div>
              <p className="sourceSnippet">{item.snippet}</p>
            </div>
          );
        })}
      </div>
    </details>
  );
}

function Chat() {
  const { newChat, prevChats, reply } = useContext(MyContext);
  const [latestReply, setLatestReply] = useState(null);

  useEffect(() => {
    if (reply === null) {
      setLatestReply(null);
      return;
    }
    if (!prevChats?.length) return;
    const content = reply.split(" "); //individual words

    let idx = 0;
    const interval = setInterval(() => {
      setLatestReply(content.slice(0, idx + 1).join(" "));
      idx++;
      if (idx >= content.length) clearInterval(interval);
    }, 40);
    return () => clearInterval(interval);
  }, [prevChats, reply]);

  const lastChat = prevChats?.length > 0 ? prevChats[prevChats.length - 1] : null;

  return (
    <>
      {newChat && <h1>Where Should We Begin?</h1>}
      <div className="chats">
        {prevChats?.slice(0, -1).map((chat, idx) => (
          <div
            className={chat.role === "user" ? "userDiv" : "gptDiv"}
            key={idx}
          >
            {chat.role === "user" ? (
              <p className="userMessage">{chat.content}</p>
            ) : (
              <>
                <ReactMarkdown rehypePlugins={[RehypeHighlight]}>
                  {chat.content}
                </ReactMarkdown>
                <SourcesList sources={chat.sources} />
              </>
            )}
          </div>
        ))}
        {lastChat && (
          <>
            {latestReply === null ? (
              <div className="gptDiv" key={"not-typing"}>
                <ReactMarkdown rehypePlugins={[RehypeHighlight]}>
                  {lastChat.content}
                </ReactMarkdown>
                <SourcesList sources={lastChat.sources} />
              </div>
            ) : (
              <div className="gptDiv" key={"typing"}>
                <ReactMarkdown rehypePlugins={[RehypeHighlight]}>
                  {latestReply}
                </ReactMarkdown>
                <SourcesList sources={lastChat.sources} />
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}

export default Chat;
