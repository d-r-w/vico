"use client";

import { useRef, useState } from "react";
import { TagSidebar } from "@/app/components/tag-sidebar";
import { ClientWrapper } from "@/app/components/client-wrapper";
import { Tag } from "@/app/types";
import { 
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
  ImperativePanelHandle
} from "@/components/ui/resizable";

interface SidebarLayoutProps {
  tags: Tag[];
  initialSearch: string;
  children: React.ReactNode;
}

export function SidebarLayout({ tags, initialSearch, children }: SidebarLayoutProps) {
  const sidebarRef = useRef<ImperativePanelHandle>(null);
  const [isCollapsed, setIsCollapsed] = useState(true);

  const toggleSidebar = () => {
    const panel = sidebarRef.current;
    if (panel) {
      if (isCollapsed) {
        panel.expand();
        setIsCollapsed(false);
      } else {
        panel.collapse();
        setIsCollapsed(true);
      }
    }
  };

  return (
    <ResizablePanelGroup direction="horizontal" className="flex-1">
      <ResizablePanel 
        ref={sidebarRef}
        defaultSize={0} 
        minSize={15} 
        maxSize={25}
        collapsible={true}
        collapsedSize={0}
        onCollapse={() => setIsCollapsed(true)}
        onExpand={() => setIsCollapsed(false)}
      >
        <TagSidebar tags={tags} />
      </ResizablePanel>
      <ResizableHandle withHandle />
      <ResizablePanel defaultSize={100}>
        <ResizablePanelGroup direction="vertical" className="flex-1">
          <ResizablePanel defaultSize={40} minSize={25}>
            <ClientWrapper 
              initialSearch={initialSearch} 
              onToggleSidebar={toggleSidebar}
            />
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize={60}>
            {children}
          </ResizablePanel>
        </ResizablePanelGroup>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}


