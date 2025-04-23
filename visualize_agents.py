from agents.extensions.visualization import draw_graph
from ai_trade_agent import main_agent

def main():
    # Show the agent graph in a separate window
    draw_graph(main_agent).view()
    # Or, to save as a file:
    # draw_graph(main_agent, filename="agent_graph.png")

if __name__ == "__main__":
    main()
