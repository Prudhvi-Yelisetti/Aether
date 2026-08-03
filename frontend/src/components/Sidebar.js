export default function Sidebar({
  projects,
  currentProject,
  onSelectProject,
  onCreateProject,
  chatList,
  currentChat,
  onSelectChat,
  onNewChat,
  onOpenCapabilities,
  onOpenMemory,
  onOpenSettings,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark">Æ</span>
        <span className="brand-name">Aether</span>
      </div>

      <button className="btn-capabilities" onClick={onOpenCapabilities}>
        ⌘ Capabilities
      </button>

      {currentProject && (
        <button className="btn-capabilities" onClick={onOpenMemory}>
          ⌘ Memory
        </button>
      )}

      <button className="btn-capabilities" onClick={onOpenSettings}>
        ⌘ Settings
      </button>

      <div className="sidebar-section">
        <div className="sidebar-section-header">
          <h3>Projects</h3>
          <button className="btn-new" onClick={onCreateProject} aria-label="New project">
            +
          </button>
        </div>
        <div className="sidebar-list">
          {Object.entries(projects).map(([id, proj]) => (
            <button
              key={id}
              className={`sidebar-item ${currentProject === id ? "sidebar-item-active" : ""}`}
              onClick={() => onSelectProject(id)}
            >
              {proj.name}
            </button>
          ))}
        </div>
      </div>

      {currentProject && (
        <div className="sidebar-section">
          <div className="sidebar-section-header">
            <h3>Chats</h3>
            <button className="btn-new" onClick={onNewChat} aria-label="New chat">
              +
            </button>
          </div>
          <div className="sidebar-list">
            {chatList.map((id) => (
              <button
                key={id}
                className={`sidebar-item sidebar-item-chat ${currentChat === id ? "sidebar-item-active" : ""}`}
                onClick={() => onSelectChat(id)}
              >
                chat {id}
              </button>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}
