/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.sql.Date;
import java.util.*;

// line 252 "../../model-v0.1.ump"
public class DailyLog extends CanonicalEntity
{

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //DailyLog Attributes
  private Date logDate;
  private String summary;

  //DailyLog Associations
  private Project project;
  private User author;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public DailyLog(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, Date aLogDate, Project aProject)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    logDate = aLogDate;
    summary = null;
    boolean didAddProject = setProject(aProject);
    if (!didAddProject)
    {
      throw new RuntimeException("Unable to create dailyLog due to project. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
  }

  //------------------------
  // INTERFACE
  //------------------------

  public boolean setLogDate(Date aLogDate)
  {
    boolean wasSet = false;
    logDate = aLogDate;
    wasSet = true;
    return wasSet;
  }

  public boolean setSummary(String aSummary)
  {
    boolean wasSet = false;
    summary = aSummary;
    wasSet = true;
    return wasSet;
  }

  public Date getLogDate()
  {
    return logDate;
  }

  public String getSummary()
  {
    return summary;
  }
  /* Code from template association_GetOne */
  public Project getProject()
  {
    return project;
  }
  /* Code from template association_GetOne */
  public User getAuthor()
  {
    return author;
  }

  public boolean hasAuthor()
  {
    boolean has = author != null;
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
      existingProject.removeDailyLog(this);
    }
    project.addDailyLog(this);
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setAuthor(User aAuthor)
  {
    boolean wasSet = false;
    User existingAuthor = author;
    author = aAuthor;
    if (existingAuthor != null && !existingAuthor.equals(aAuthor))
    {
      existingAuthor.removeDailyLog(this);
    }
    if (aAuthor != null)
    {
      aAuthor.addDailyLog(this);
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
      placeholderProject.removeDailyLog(this);
    }
    if (author != null)
    {
      User placeholderAuthor = author;
      this.author = null;
      placeholderAuthor.removeDailyLog(this);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "summary" + ":" + getSummary()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "logDate" + "=" + (getLogDate() != null ? !getLogDate().equals(this)  ? getLogDate().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "project = "+(getProject()!=null?Integer.toHexString(System.identityHashCode(getProject())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "author = "+(getAuthor()!=null?Integer.toHexString(System.identityHashCode(getAuthor())):"null");
  }
}