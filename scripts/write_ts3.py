import pathlib

lines = [
"  if (loading) return <div className=\"max-w-4xl mx-auto\"><div className=\"h-8 w-48 bg-gray-100 rounded-lg animate-pulse mb-4\" /><div className=\"h-96 bg-gray-100 rounded-2xl animate-pulse\" /></div>;",
"  if (units.length === 0) {",
"    return (",
"      <div className=\"max-w-2xl mx-auto\">",
"        <Card hover={false}>",
"          <EmptyState icon=\"academicCap\" title=\"没有可教学的内容\" description=\"请先上传书籍并进行知识拆分\"",
"            action={<Button onClick={() => navigate(`/books/${bookId}`)}>返回书籍详情</Button>} />",
"        </Card>",
"      </div>",
"    );",
"  }",
"  return (<div className=\"max-w-4xl mx-auto animate-fade-in\">",
"    <LearningPath units={units} viewingUnitId={viewingUnitId} currentUnitIndex={currentUnitIndex} onViewUnit={setViewingUnitId} onJumpToUnit={handleJumpToUnit} />",
"    <div className=\"flex items-center justify-between mb-6\"><div><h1 className=\"text-xl font-bold text-gray-800\">教学模式</h1><p className=\"text-xs text-gray-400 mt-0.5\">单元 {currentUnitIndex + 1} / {totalUnits} · {getPhaseLabel(currentPhase)}</p></div><div className=\"flex items-center gap-4\"><div className=\"w-40\"><ProgressBar value={completedSteps} max={totalSteps} size=\"sm\" color=\"blue\" /></div><span className=\"text-sm font-semibold text-blue-600\">{progressPercent}%</span></div></div>",
"    <div className=\"flex items-center gap-1 mb-6 overflow-x-auto pb-2\">{strategyPhases.map((phase) => {",
"      const config = PHASE_CONFIG[phase as keyof typeof PHASE_CONFIG]; if (!config) return null;",
"      const isActive = currentPhase === phase;",
"      const currentOrder = strategyPhases.indexOf(currentPhase as TeachingPhase);",
"      const thisOrder = strategyPhases.indexOf(phase);",
"      const isPast = thisOrder < currentOrder;",
"      return (<div key={phase} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium shrink-0 transition-all ${isActive ? 'bg-blue-500 text-white shadow-md shadow-blue-500/20' : isPast ? 'bg-blue-50 text-blue-600' : 'bg-gray-50 text-gray-400'}`}><span>{config.icon}</span><span>{config.label}</span></div>);",
"    })}</div>",
"    <div className=\"bg-gray-50/50 rounded-2xl mb-6 border border-gray-100\"><div className=\"flex items-center justify-between px-5 pt-4 pb-2\"><span className=\"text-xs font-semibold text-gray-400\">{units.find((u) => u.id === viewingUnitId)?.title || `单元 ${units.findIndex((u) => u.id === viewingUnitId) + 1}`}</span><div className=\"flex items-center gap-3\"><select value={viewingUnitId} onChange={(e) => setViewingUnitId(e.target.value)} className=\"text-xs text-gray-500 bg-transparent border-none outline-none cursor-pointer\">{units.map((u, i) => <option key={u.id} value={u.id}>{u.title || `单元 ${i + 1}`}</option>)}</select>{unitMessages.length > 0 && <button onClick={handleClearMessages} className=\"text-xs text-gray-400 hover:text-red-500 transition-colors\">清空记录</button>}</div></div>",
"    <div className=\"px-5 pb-5 min-h-[250px] max-h-[460px] overflow-y-auto\">{unitMessages.length === 0 ? <div className=\"flex items-center justify-center h-40 text-gray-400 text-sm\">点击继续开始学习</div> : <>{unitMessages.map((msg, i) => <MessageBubble key={msg.id || i} msg={msg} />)}<div ref={messagesEndRef} /></>}</div></div>",
"    {!completed && !awaitingAnswer && !(test && test.score !== null) && <div className=\"flex justify-end mb-4\"><Button onClick={handleAdvance} disabled={advancing}>{advancing ? '...' : '继续'}</Button></div>}",
"    {completed && !test && <Card hover={false} className=\"mb-6\"><EmptyState icon=\"checkCircle\" title=\"所有单元已学完\" description=\"完成测试来检验你的理解程度\" action={<Button onClick={handleRunTest}>开始测试</Button>} /></Card>}",
"    {test && <TestPanel test={test} onSubmit={handleSubmitTest} />}",
]

p = pathlib.Path(r"E:/AI Agent/work area/Studying-helper/frontend/src/pages/TeachingSession.tsx")
p.write_text(p.read_text(encoding="utf-8") + "\n".join(lines), encoding="utf-8")
print("part3 done")
