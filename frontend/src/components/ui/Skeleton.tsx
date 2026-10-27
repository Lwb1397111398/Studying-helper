// 骨架屏组件：替代全屏 Loading 转圈
export function SkeletonBlock({ className = '' }: { className?: string }) {
  return <div className={`bg-gray-100 rounded-lg animate-pulse ${className}`} />;
}

/** 首页骨架：横幅 + 统计卡 + 书籍卡片栅格 */
export function HomeSkeleton() {
  return (
    <div>
      <SkeletonBlock className="h-32 rounded-2xl mb-8" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[0, 1, 2, 3].map(i => <SkeletonBlock key={i} className="h-28 rounded-2xl" />)}
      </div>
      <SkeletonBlock className="h-6 w-32 mb-5" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[0, 1, 2].map(i => <SkeletonBlock key={i} className="h-36 rounded-2xl" />)}
      </div>
    </div>
  );
}

/** 书籍详情骨架：头部横幅 + 进度卡 + 章节列表 */
export function BookOverviewSkeleton() {
  return (
    <div className="max-w-4xl mx-auto">
      <SkeletonBlock className="h-40 rounded-2xl mb-8" />
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[0, 1, 2].map(i => <SkeletonBlock key={i} className="h-20 rounded-2xl" />)}
      </div>
      <div className="space-y-3">
        {[0, 1, 2, 3].map(i => <SkeletonBlock key={i} className="h-24 rounded-2xl" />)}
      </div>
    </div>
  );
}

/** 目录编辑骨架 */
export function TocSkeleton() {
  return (
    <div className="max-w-5xl mx-auto">
      <SkeletonBlock className="h-10 w-48 mb-6" />
      <div className="space-y-2">
        {[0, 1, 2, 3, 4, 5].map(i => <SkeletonBlock key={i} className="h-14 rounded-xl" />)}
      </div>
    </div>
  );
}
