/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.sql.Date;
import java.util.*;

/**
 * Tasks and DailyLogs are owned by their Project — if the project is purged
 * from the canonical layer they go too. Compositions also make the
 * "every task has exactly one project" lifecycle invariant enforceable.
 */
// line 257 "../../model-v0.1.ump"
public class Task extends CanonicalEntity
{

  //------------------------
  // ENUMERATIONS
  //------------------------

  public enum TaskStatus { TODO, IN_PROGRESS, BLOCKED, DONE, CANCELLED }

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Task Attributes
  private String title;
  private TaskStatus status;
  private Date dueDate;
  private Date completedAt;

  //Task Associations
  private Project project;
  private User assignee;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Task(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aTitle, Project aProject)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    title = aTitle;
    dueDate = null;
    completedAt = null;
    boolean didAddProject = setProject(aProject);
    if (!didAddProject)
    {
      throw new RuntimeException("Unable to create task due to project. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
  }

  //------------------------
  // INTERFACE
  //------------------------

  public boolean setTitle(String aTitle)
  {
    boolean wasSet = false;
    title = aTitle;
    wasSet = true;
    return wasSet;
  }

  public boolean setStatus(TaskStatus aStatus)
  {
    boolean wasSet = false;
    status = aStatus;
    wasSet = true;
    return wasSet;
  }

  public boolean setDueDate(Date aDueDate)
  {
    boolean wasSet = false;
    dueDate = aDueDate;
    wasSet = true;
    return wasSet;
  }

  public boolean setCompletedAt(Date aCompletedAt)
  {
    boolean wasSet = false;
    completedAt = aCompletedAt;
    wasSet = true;
    return wasSet;
  }

  public String getTitle()
  {
    return title;
  }

  public TaskStatus getStatus()
  {
    return status;
  }

  public Date getDueDate()
  {
    return dueDate;
  }

  public Date getCompletedAt()
  {
    return completedAt;
  }
  /* Code from template association_GetOne */
  public Project getProject()
  {
    return project;
  }
  /* Code from template association_GetOne */
  public User getAssignee()
  {
    return assignee;
  }

  public boolean hasAssignee()
  {
    boolean has = assignee != null;
    return has;
  }
  /* Code from template association_SetOneToMany */
  public boolean setProject(Project aProject)
  {
    boolean wasSet = false;
    if (aProject == null)
    {
      return wasSet;
    }

    Project existingProject = project;
    project = aProject;
    if (existingProject != null && !existingProject.equals(aProject))
    {
      existingProject.removeTask(this);
    }
    project.addTask(this);
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setAssignee(User aAssignee)
  {
    boolean wasSet = false;
    User existingAssignee = assignee;
    assignee = aAssignee;
    if (existingAssignee != null && !existingAssignee.equals(aAssignee))
    {
      existingAssignee.removeTask(this);
    }
    if (aAssignee != null)
    {
      aAssignee.addTask(this);
    }
    wasSet = true;
    return wasSet;
  }

  public void delete()
  {
    Project placeholderProject = project;
    this.project = null;
    if(placeholderProject != null)
    {
      placeholderProject.removeTask(this);
    }
    if (assignee != null)
    {
      User placeholderAssignee = assignee;
      this.assignee = null;
      placeholderAssignee.removeTask(this);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "title" + ":" + getTitle()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "status" + "=" + (getStatus() != null ? !getStatus().equals(this)  ? getStatus().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "dueDate" + "=" + (getDueDate() != null ? !getDueDate().equals(this)  ? getDueDate().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "completedAt" + "=" + (getCompletedAt() != null ? !getCompletedAt().equals(this)  ? getCompletedAt().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "project = "+(getProject()!=null?Integer.toHexString(System.identityHashCode(getProject())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "assignee = "+(getAssignee()!=null?Integer.toHexString(System.identityHashCode(getAssignee())):"null");
  }
}